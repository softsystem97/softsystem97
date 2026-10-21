"""Exercise Frappe scheduler -> default worker -> local SMTP, without external mail.

Requires aiosmtpd==1.4.6 and local redis-server. Only disposable audit/test
sites with allow_tests are accepted. This validates Frappe infrastructure, not the
legacy SS97 ticket confirmation producer. --bridge exercises the replacement producer. Run from the bench directory.
"""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
from email import policy as email_policy
from email.parser import BytesParser, Parser
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

import frappe
from aiosmtpd.controller import Controller
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError


@contextmanager
def isolated_background_queue(log_file):
    """Use a new loopback Redis process, never drain or purge an existing queue.

    FRAPPE_REDIS_QUEUE is an official Frappe configuration override inherited by
    the scheduler/worker. No Redis endpoint/credential is written to site config.
    """
    from frappe.config import clear_site_config_cache
    from frappe.utils import background_jobs

    binary = shutil.which('redis-server')
    if not binary:
        raise RuntimeError('Local redis-server required for an isolated SMTP probe')
    if frappe.conf.get('use_rq_auth') or frappe.conf.get('redis_queue_sentinel_enabled'):
        raise RuntimeError('This disposable probe requires plain local Redis queue configuration')
    old_env = os.environ.get('FRAPPE_REDIS_QUEUE')
    old_url = frappe.conf.redis_queue
    old_connection = background_jobs._redis_queue_conn
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen([binary, '--bind', '127.0.0.1', '--port', str(port),
        '--save', '', '--appendonly', 'no'], stdout=log_file, stderr=log_file)
    client = Redis(host='127.0.0.1', port=port, socket_connect_timeout=0.2, socket_timeout=0.2)
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                if client.ping():
                    break
            except RedisConnectionError:
                pass
            except OSError:
                pass
            if process.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Isolated queue did not start; inspect local process log')
            time.sleep(0.05)
        os.environ['FRAPPE_REDIS_QUEUE'] = f'redis://127.0.0.1:{port}'
        clear_site_config_cache()
        frappe.conf.redis_queue = os.environ['FRAPPE_REDIS_QUEUE']
        background_jobs._redis_queue_conn = None
        yield
    finally:
        connection = background_jobs._redis_queue_conn
        if connection is not None and connection is not old_connection:
            connection.close()
        if old_env is None:
            os.environ.pop('FRAPPE_REDIS_QUEUE', None)
        else:
            os.environ['FRAPPE_REDIS_QUEUE'] = old_env
        clear_site_config_cache()
        frappe.conf.redis_queue = old_url
        background_jobs._redis_queue_conn = old_connection
        client.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


class Sink:
    def __init__(self):
        self.received = threading.Event()
        self.count = 0
        self.deliveries = []

    async def handle_DATA(self, server, session, envelope):
        message = BytesParser(policy=email_policy.default).parsebytes(envelope.content)
        subject = str(message.get('Subject', ''))
        self.deliveries.extend((subject, recipient) for recipient in envelope.rcpt_tos)
        self.count += 1
        self.received.set()
        return '250 local audit accepted'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True)
    parser.add_argument('--bridge', action='store_true', help='Exercise the opt-in replacement bridge producer')
    args = parser.parse_args()
    if not args.site.startswith(('audit.', 'test_')):
        parser.error('Disposable audit/test site required')
    bench = Path.cwd().resolve()
    os.chdir(bench / 'sites')
    frappe.init(site=args.site, sites_path=str(bench / 'sites'))
    frappe.connect()
    frappe.set_user('Administrator')
    if not frappe.conf.allow_tests:
        raise RuntimeError('allow_tests must be enabled on the disposable site')
    if frappe.db.exists('Email Account', {'enable_outgoing': 1}):
        raise RuntimeError('Refusing to change a site with an existing outgoing account')
    if frappe.db.exists('Email Queue', {'status': ['in', ['Not Sent', 'Sending', 'Error']]}):
        raise RuntimeError('Probe requires an empty pending mail queue on the disposable site')
    # Never copy a site_config file or retrieve any account password/API credentials.
    sink = Sink()
    smtp = Controller(sink, hostname='127.0.0.1', port=8026)
    processes = []
    queue_scope = ExitStack()
    smtp_started = False
    created = []
    config_fields = ['mute_emails', 'scheduler_tick_interval', 'scheduler_interval', 'pause_scheduler']
    # Preserve key presence as well as values; merged defaults are not site settings.
    site_path = bench / 'sites' / args.site / 'site_config.json'
    site_values = json.loads(site_path.read_text())
    old_conf = {field: (field in site_values, site_values.get(field)) for field in config_fields}
    del site_values
    old_enabled = frappe.db.get_single_value('System Settings', 'enable_scheduler')
    common_config_path = str(bench / 'sites' / 'common_site_config.json')
    common_values = json.loads(Path(common_config_path).read_text())
    old_tick = ("scheduler_tick_interval" in common_values, common_values.get('scheduler_tick_interval'))
    del common_values
    method = 'frappe.email.queue.flush'
    job = frappe.get_doc('Scheduled Job Type', {'method': method})
    old_job = {field: job.get(field) for field in ['stopped', 'last_execution', 'create_log']}
    prior_completed_logs = set(frappe.get_all('Scheduled Job Log', filters={
        'scheduled_job_type': job.name, 'status': 'Complete'}, pluck='name'))
    log_path = bench / 'logs' / 'audit-mail-processes.log'
    log_file = log_path.open('w')
    from frappe.utils.background_jobs import get_queue
    previous_queue = get_queue('default')
    previous_jobs = previous_queue.get_job_ids()
    try:
        queue_scope.enter_context(isolated_background_queue(log_file))
        smtp.start()
        smtp_started = True
        # The scheduler reads its tick from bench config before initializing a site.
        frappe.installer.update_site_config('scheduler_tick_interval', 1,
                                             site_config_path=common_config_path)
        for key, value in dict(mute_emails=False, scheduler_tick_interval=1,
                               scheduler_interval=60, pause_scheduler=False).items():
            frappe.conf[key] = value
            frappe.installer.update_site_config(key, value)
        frappe.db.set_single_value('System Settings', 'enable_scheduler', 1)
        frappe.db.set_value(job.doctype, job.name, dict(stopped=0, create_log=1,
                             last_execution=frappe.utils.add_to_date(None, minutes=-5)))
        account = frappe.get_doc(dict(doctype='Email Account', email_account_name='SS97 Local Audit',
                     email_id='sender@example.invalid', enable_outgoing=1, default_outgoing=1,
                     smtp_server='127.0.0.1', smtp_port=8026, use_tls=0,
                     no_smtp_authentication=1)).insert()
        created.append((account.doctype, account.name))
        if args.bridge:
            from bridge_mail_fixture import produce
            issue = produce(account, created)
            expected_count = 6  # opening, assignment, resolution and closure (two recipients each).
        else:
            notification = frappe.get_doc(dict(doctype='Notification',
                name='SS97 Local Audit Confirmation', document_type='Issue', event='New',
                channel='Email', enabled=1, subject='SS97 isolated confirmation probe',
                message='Local synthetic probe only',
                recipients=[dict(receiver_by_document_field='raised_by')])).insert()
            created.append((notification.doctype, notification.name))
            issue = frappe.get_doc(dict(doctype='Issue', subject='SS97 isolated mail audit',
                                        raised_by='recipient@example.invalid')).insert()
            created.append((issue.doctype, issue.name))
            expected_count = 1
        queued = frappe.get_all('Email Queue', filters={'reference_doctype': 'Issue',
                                 'reference_name': issue.name}, pluck='name')
        assert len(queued) == expected_count, 'Unexpected notification count'
        for name in queued:
            created.append(('Email Queue', name))
            frappe.db.set_value('Email Queue', name, 'creation',
                                frappe.utils.add_to_date(None, seconds=-20), update_modified=False)
        expected_deliveries = Counter()
        for name in queued:
            mail = frappe.get_doc('Email Queue', name)
            subject = str(Parser(policy=email_policy.default).parsestr(mail.message).get('Subject', ''))
            expected_deliveries.update((subject, recipient.recipient) for recipient in mail.recipients)
        frappe.db.commit()
        assert all(frappe.db.get_value('Email Queue', name, 'status') == 'Not Sent' for name in queued)
        assert not sink.received.is_set()
        producer = 'replacement bridge with repeated requests' if args.bridge else 'native Notification'
        print(f'PASS {producer} -> Email Queue: {expected_count} Not Sent, no duplicates', flush=True)
        # Use real processes and the registered scheduler; never call flush or Send Now here.
        for command in [['bench', 'worker', '--queue', 'default'], ['bench', 'schedule']]:
            processes.append(subprocess.Popen(command, cwd=bench, stdout=log_file, stderr=log_file))
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline:
            frappe.db.rollback()
            statuses = [frappe.db.get_value('Email Queue', name, 'status') for name in queued]
            completed_logs = set(frappe.get_all('Scheduled Job Log', filters={
                'scheduled_job_type': job.name, 'status': 'Complete'}, pluck='name'))
            new_completed_logs = completed_logs - prior_completed_logs
            if sink.received.is_set() and all(status == 'Sent' for status in statuses) and new_completed_logs:
                break
            if any(p.poll() is not None for p in processes):
                raise AssertionError('Scheduler or worker exited; inspect local process log')
            time.sleep(0.5)
        assert all(status == 'Sent' for status in statuses) and sink.count == expected_count, (statuses, sink.count)
        assert Counter(sink.deliveries) == expected_deliveries, 'Unexpected subject/recipient or duplicate delivery'
        assert new_completed_logs, 'No new completed scheduler execution was observed'
        print(f'PASS autonomous scheduler -> worker -> local SMTP: {expected_count} Sent, exactly once each', flush=True)
    finally:
        for proc in reversed(processes):
            proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if smtp_started:
            smtp.stop()
        try:
            frappe.set_user('Administrator')
            frappe.db.rollback()
            for doctype, name in reversed(created):
                if frappe.db.exists(doctype, name):
                    frappe.delete_doc(doctype, name)
            frappe.db.set_value(job.doctype, job.name, old_job)
            frappe.db.set_single_value('System Settings', 'enable_scheduler', old_enabled)
            for key, (present, value) in old_conf.items():
                frappe.installer.update_site_config(key, value if present else 'None')
            frappe.installer.update_site_config('scheduler_tick_interval', old_tick[1] if old_tick[0] else 'None',
                                                 site_config_path=common_config_path)
            frappe.db.commit()
        finally:
            try:
                queue_scope.close()
                assert previous_queue.get_job_ids() == previous_jobs, 'Existing queue changed; run this probe exclusively'
                restored_site = json.loads(site_path.read_text())
                assert {key: (key in restored_site, restored_site.get(key)) for key in config_fields} == old_conf
                restored_common = json.loads(Path(common_config_path).read_text())
                assert ('scheduler_tick_interval' in restored_common,
                        restored_common.get('scheduler_tick_interval')) == old_tick
                print('PASS original queue unchanged; temporary configuration restored', flush=True)
            finally:
                log_file.close()
                frappe.destroy()


if __name__ == '__main__':
    import frappe.installer
    main()
