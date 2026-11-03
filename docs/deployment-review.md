# Controlled deployment review

This change hardens Bridge and notification permissions. It does not implement or replace a technician portal. Custom ticket workflows must be supplied privately and validated against the actual installed application versions before claiming incident resolution.

## Scope and compatibility

- Bridge mutations and notification mutations require POST. Existing clients that write with GET must be adapted before rollout.
- Bridge service users need native create/read/write permissions on `SS97 Bridge Request`. Do not automatically grant System Manager; an authorized administrator must review a dedicated least privilege role.
- Customer notification permissions use `for_user`, not the producing document owner. Customer cannot create notifications. Existing Custom DocPerm and document shares must be reviewed on staging: a standard JSON migration does not necessarily replace custom permissions.
- No data patch, column deletion, credential rotation, or new public endpoint is included. Diagnostic collection is bench-only and requires System Manager; target queue/user identifiers are supplied by the operator, not embedded in source.
- Local validation uses Frappe/ERPNext v16. Validate the exact deployed patch versions and the full custom application list on staging. Tests on a newer v16 patch do not establish compatibility with every v16 patch.

## Staging gate

1. Record the reviewed commit and currently deployed app commits. Inspect the complete diff and approve the scope.
2. Provision an authorized staging copy through the site's Frappe Cloud workflow, with outbound mail routed to a controlled sink and production integrations disabled by the operator. Do not import credentials into development or publish site exports.
3. Have the authorized operator record the existing permissions and customizations. Preserve the ticket/technician code; do not replace it with a second ticket implementation.
4. Build the reviewed app commit on the compatible private bench using Frappe Cloud's build/deploy UI. Verify successful app installation, asset build and migration in the deployment logs. Do not switch the production branch or merge automatically.
5. On a disposable test site with `allow_tests`, run from the bench directory:

```bash
./env/bin/python apps/softsystem97/tools/run_local_tests.py --site test_review
```

The test runner creates and removes synthetic users/documents. Never run it on a business or production site. It requires real Frappe, ERPNext, MariaDB and Redis. The standalone SMTP probe additionally requires `aiosmtpd==1.4.6`, a disposable site and no existing outgoing account:

```bash
./env/bin/python apps/softsystem97/tools/validate_local_mail.py --site test_review
```

The probe temporarily creates a native Notification rule for synthetic Issue creation. It verifies the native chain, not an absent custom confirmation producer. It restores its scheduler settings and stops only its own processes. Run it without another test runner concurrently. Drain old synthetic jobs using the normal worker before a timed probe; never purge a business queue.

6. Use the real imported technician code for the acceptance matrix: Client A creates a ticket; technician A is assigned and notified; A sees the ticket; unassigned B and a user from another company are denied; expired/Guest session is denied; administrator can follow status; exactly one confirmation is queued and delivered automatically. Record any missing scenario as unrun.
7. Inspect Bridge duplicate handling, invalid results, notification ownership, all-pages mark-read and native Notification Log fallback. Verify existing commercial workflows separately; the focused suite is not a complete ERP regression suite.

## Production gate — human approval required

Do not proceed until the owner approves the exact release commit, changes to production permissions/configuration, the backup, the maintenance window and rollback owner. Passing local tests alone does not satisfy this gate.

1. In Frappe Cloud, request a fresh backup of the database, public files and private files using the site's supported backup controls. Confirm successful completion, timestamp and availability to the authorized operator. Preserve platform-managed restoration configuration securely. Do not download backups or encryption material into Git or chat. A backup has not been made by the development agent.
2. Confirm a supported restore procedure on staging and retain the previous working build. Avoid upgrading Frappe/ERPNext as part of this focused patch unless separately reviewed.
3. After approval, the operator selects the reviewed app commit/source branch on the correct private bench and launches the Frappe Cloud build/deployment. Monitor build and migration results before reopening normal operations. UI labels vary by plan; ask support if the deployment controls are unavailable.
4. Post-release, use a controlled acceptance ticket and approved recipients, then verify the same role/isolation matrix, automatic delivery, queue state and Scheduled Job Log. Never replay or flush the whole business mail queue merely to test one message.
5. An authorized administrator checks User permlevel 1, System Manager access to native Generate Keys, Client Scripts and Property Setters. Do not reset all User permissions. Credential generation/rotation is a separate explicitly approved operation performed by the owner in the UI.
6. After authorization to use newly generated credentials, the owner runs `python tools/check_rest_auth.py --base-url https://<authorized-origin>` in an interactive terminal. Values are entered without echo and are not saved. The script refuses redirects. No developer needs to receive the credentials. Positive token authentication is not established until this step succeeds.

## Rollback

Stop the rollout on failed migration, unauthorized access, mail duplication, or loss of legitimate access. The operator restores the previous approved application artifact and exact permission settings via the supported Frappe Cloud process, initially on staging. No database restoration is intrinsically required by this patch because no data columns are removed; do not overwrite new business data casually. Restoring the old code also restores the previous access defects, so any temporary isolation of the Bridge requires explicit owner approval. Coordinate any unrelated database restore with support and verify data timestamps and files together.

## Private code intake

On the Windows machine, the owner can list candidate paths without printing file contents:

```powershell
Set-Location C:\soft-system-97
rg --files -g '*.py' -g '*.js' -g '*.html' -g '*.json' -g '!node_modules/**' -g '!sites/**' -g '!**/.env*' -g '!**/*secret*' -g '!**/*credential*' |
  Select-String -Pattern 'ticket|technici|issue|assign|notification|hooks'
```

Then identify the Python/JS/HTML route handlers for technician tickets, authentication/active-state checks, creation/assignment/status APIs and notification producer. Have the owner inspect and redact embedded credentials locally before copying selected source files into a private authorized workspace or private attachment. Include redacted metadata for the actual ticket/technician DocTypes, Assignment Rules, Workflow, User Permissions, Web Form and relevant Server Scripts. Do not copy `.env`, site_config, database/files backups, tokens, user records or the whole Windows directory. Do not push private customizations into this public repository. After intake, map the original file names and review a diff before integrating anything.
