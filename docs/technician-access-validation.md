# Existing technician access: authorized validation

These diagnostics do not repair or replace a custom technician portal whose source is absent. They add no HTTP endpoint, create no account/role, change no password/assignment and send no message. Never deploy solely to collect production evidence. Use a reviewed staging installation, or have an already-authorized operator inspect equivalent fields with the platform's existing tools. Results are private account metadata and must not be committed or posted publicly.

## Confirm the actual application policy

Retrieve the existing source files privately, preserving their original paths:

- `integrations/ss97_client_support/client_ticket_api.py`
- `integrations/ss97_client_support/ticket_workspace.py`
- `integrations/ss97_client_ops/ticket_types.py`

Also obtain the actual technician route HTML/JS/Python, role/active-profile checks, relevant DocType metadata, assignment rules and notification producer. Do not infer the expected role from a proposed role name in documentation. `Candidat SS97` is not a technician role. A role label alone is not proof that a User is linked to an active technician profile.

The existing Windows discovery script emits paths only. Have the owner review/redact selected sources locally, then transfer them through an authorized private channel; never copy the entire project, environment files, database, credentials or private keys into this public repository.

## Existing account: administrative checks

1. Open the existing User document through an already-authorized administrative session. Record only enabled status, user type, role names and the required profile linkage. Do not recreate the user, reset the password or grant System Manager. Check the requested display name separately, without changing it until authorized.
2. A Website User is not automatically invalid for a website portal; a System User is needed for Desk access. Read the actual portal code before declaring either user type the cause.
3. Verify the exact role and profile active-field required by that code, and its User/organization linkage. If the role is genuinely missing, prepare its exact Role and minimum DocPerm/User Permission configuration for review only after the source policy is established. Do not apply a guessed role or blanket ticket permissions.
4. Resolve the test ticket's public reference to its actual DocType/internal name using authorized site metadata. Do not assume the public reference is `Issue.name`.
5. Compare the native document read/write permissions, the actual assignment and the custom portal query restrictions. A native read grant does not prove that a custom endpoint permits access; a broad Support Team role does not prove assignment-only isolation.

When this reviewed helper is available in a compatible authorized bench, it can inspect an existing user without impersonation:

```bash
bench --site <authorized-staging-site> execute softsystem97.diagnostics.technician_access --kwargs '{"user":"<existing-user>","ticket_doctype":"<confirmed-doctype>","ticket_name":"<internal-name>"}'
```

The helper requires the operator's System Manager role; it never grants that role to the target. It reports enabled/user_type, role names, assignment-notification preferences, native read/write and the open ToDo count for this single document. `portal_role_policy` stays unknown, `technician_profile_active` stays null and `browser_session_verified` stays false until independently checked against the real application/browser. Missing accounts are reported, never created. No Session/token tables or API credentials are read.

## Session and redirects: owner-controlled browser test

The owner signs in using the already-defined password without sharing it. In a private browser window, open the portal and check whether login returns to the intended internal route. Use the native read-only `frappe.auth.get_logged_user` endpoint from the same browser session to distinguish Guest/expired session from the expected existing identity. Do not copy cookies, request headers, HAR archives, passwords or tokens into an issue/report. Inspect JavaScript errors and server logs locally, then redact them before sharing. Without that session and the portal source, no technician-login success is established by the bench helper.

## E-mail producer and queue conditions

If support confirms the scheduler/Workers, next inspect the producer, Notification conditions/preferences, the exact pending record's send_after/error presence and selected outgoing-account flags. Do not infer that all queued messages should be replayed. This one-record helper performs no send or retry:

```bash
bench --site <authorized-staging-site> execute softsystem97.diagnostics.queued_mail_conditions --kwargs '{"queue_name":"<one-approved-email-queue-name>"}'
```

It reports whether status/send_after/creation satisfy the standard selection conditions, suspension/mute flags, error presence without error content, and enable_outgoing/default_outgoing for an explicitly linked account. A missing explicit account does not mean SMTP is unconfigured: sender/default selection may supply it, and this helper deliberately does not load credentials or verify SMTP delivery. Compare the producer's actual conditions, transaction commit and recipient settings in the existing application. Inspect error text only in the authorized site UI and redact it; never mass-flush the queue.

## Final acceptance before any production claim

Use staging with the real imported portal code first. Then, only after review, backup and explicit production authorization:

- Existing owner logs in with their unchanged password; role/profile and landing route are correct.
- A controlled customer creates one ticket through the real client flow; exactly one request and intended assignment exist.
- The authorized active technician sees it in the actual portal, can take charge and perform allowed status updates; client tracking reflects them.
- Another unassigned technician/company and an expired/Guest session are denied.
- Customer confirmation and technician assignment notification occur automatically and reach approved recipients once; no old-mail bulk replay.
- Administrator follows the history; no global permission, account or password reset occurred.

Record performed, failed and unrun outcomes separately. The infrastructure tests and native Issue/ToDo baseline do not validate the custom portal. Retain the deployment and rollback gate in `docs/deployment-review.md`.
