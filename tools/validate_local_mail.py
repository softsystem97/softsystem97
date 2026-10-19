"""Exercise Frappe scheduler -> default worker -> local SMTP, without external mail.

Requires aiosmtpd==1.4.6 in the bench Python environment. Only disposable audit/test
sites with allow_tests are accepted. This validates Frappe infrastructure, not the
legacy SS97 ticket confirmation producer. --bridge exercises the replacement producer. Run from the bench directory.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading
import time

import frappe
from aiosmtpd.controller import Controller


class Sink:
    def __init__(self):
        self.received = threading.Event()
        self.count = 0

    async def handle_DATA(self, server, session, envelope):
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
    if args.bridge and frappe.db.exists('Email Queue', {'status': ['in', ['Not Sent', 'Sending', 'Error']]}):
        raise RuntimeError('Bridge probe requires an empty pending mail queue on the disposable site')
    # Never copy a site_config file or retrieve any account password/API credentials.
    sink = Sink()
    smtp = Controller(sink, hostname='127.0.0.1', port=8026)
    processes = []
    created = []
    config_fields = ['mute_emails', 'scheduler_tick_interval', 'scheduler_interval', 'pause_scheduler']
    old_conf = {field: frappe.conf.get(field) for field in config_fields}
    old_enabled = frappe.db.get_single_value('System Settings', 'enable_scheduler')
    common_config_path = str(bench / 'sites' / 'common_site_config.json')
    old_tick = json.loads(Path(common_config_path).read_text()).get('scheduler_tick_interval')
    method = 'frappe.email.queue.flush'
    job = frappe.get_doc('Scheduled Job Type', {'method': method})
    old_job = {field: job.get(field) for field in ['stopped', 'last_execution', 'create_log']}
    log_path = bench / 'logs' / 'audit-mail-processes.log'
    log_file = log_path.open('w')
    try:
        smtp.start()
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
            if sink.received.is_set() and all(status == 'Sent' for status in statuses):
                break
            if any(p.poll() is not None for p in processes):
                raise AssertionError('Scheduler or worker exited; inspect local process log')
            time.sleep(0.5)
        assert all(status == 'Sent' for status in statuses) and sink.count == expected_count, (statuses, sink.count)
        assert frappe.db.exists('Scheduled Job Log', {'scheduled_job_type': job.name, 'status': 'Complete'})
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
        smtp.stop()
        log_file.close()
        frappe.set_user('Administrator')
        frappe.db.rollback()
        for doctype, name in reversed(created):
            if frappe.db.exists(doctype, name):
                frappe.delete_doc(doctype, name)
        frappe.db.set_value(job.doctype, job.name, old_job)
        frappe.db.set_single_value('System Settings', 'enable_scheduler', old_enabled)
        for key, value in old_conf.items():
            frappe.installer.update_site_config(key, value)
        frappe.installer.update_site_config('scheduler_tick_interval', old_tick,
                                             site_config_path=common_config_path)
        frappe.db.commit()
        frappe.destroy()


if __name__ == '__main__':
    import frappe.installer
    main()
