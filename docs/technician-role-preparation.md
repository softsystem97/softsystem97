# Technician role preparation — explicit and idempotent

These tools are **not** registered in install hooks, scheduler hooks, HTTP endpoints or patches.txt. Installing/updating the application does not create a role or change a real User. The missing custom portal policy still prevents an operational technician permission configuration. No replacement ticket system is introduced.

## Read-only preparation on an authorized staging bench

An already-authorized System Manager operator can list **all** Role records, without a filtered/paginated role-name search:

```bash
bench --site <authorized-staging-site> execute softsystem97.provisioning.role_inventory
```

Reuse the exact compatible role required by the recovered portal code when it exists. `Candidat SS97` is never a substitute. Neither the proposed `SS97 Technicien` label nor User.enabled proves an active technician profile. Inspect the existing profile's User/organization linkage, active field and route/API checks from the actual sources first.

The fallback role proposed by the owner is simulated by default:

```bash
bench --site <authorized-staging-site> execute softsystem97.provisioning.prepare_technician_role
```

If absent, the simulation proposes `SS97 Technicien`, custom role, **desk_access=0**. If a role already exists, its disabled/Desk/permission settings are preserved. A website portal does not automatically require Desk access. The simulation creates nothing and never assigns a User or DocPerm.

Only after the real policy is confirmed, the intended role name reviewed and the operation explicitly authorized, the operator can apply role-only creation on staging:

```bash
bench --site <authorized-staging-site> execute softsystem97.provisioning.prepare_technician_role --kwargs '{"dry_run":false,"policy_confirmed":true}'
```

Use `role_name` only for an exact compatible name established by source review. Repeated execution does not duplicate the role or rewrite existing settings. Candidate/admin/builtin catch-all roles cannot be selected. Booleans must be JSON booleans, not strings. The operation does not commit early; the authorized bench runner owns the transaction. Production use requires its own explicit approval and normal backup/deployment safeguards.

**Creating this role alone does not enable the technician portal.** No global Issue read/write/delete, System Manager, API-key permission or assignment is granted. Do not create broad DocPerm merely to make an access error disappear.

## Existing-user change plan

```bash
bench --site <authorized-staging-site> execute softsystem97.provisioning.plan_existing_user --kwargs '{"user":"<existing-user>","desired_last_name":"<approved-last-name>"}'
```

This returns only the current first/last name, enabled/type, role names and proposed last-name difference. It never saves a User, renames a login, creates a missing account, sets a password or assigns a role. Repeating the call produces the same plan while the underlying account remains unchanged. Keep the result private. Any approved real account update must be performed by the authorized operator through the existing User UI; no code here applies it.

## Permission configuration pending actual portal sources

Before assigning the confirmed role, prepare a reviewed matrix for the **existing** ticket DocType and profile model:

| Operation | Intended boundary | Required source evidence |
| --- | --- | --- |
| Login/portal | Valid session, enabled User and required active profile | Real route and profile checks, login redirect behavior |
| Ticket list/read | Assigned/explicitly authorized tickets and required customer data only | Assignment model, document hooks/query conditions, company/user restrictions |
| Status update | Allowed transitions on authorized tickets only | Existing status/workflow controller and server-side permission checks |
| Comments/reports | Authorized ticket and permitted fields only | Existing comment/report API and referenced-document checks |
| Notifications | Recipient's notifications and approved delivery preferences | Existing producer, preferences and after-commit behavior |
| Delete/admin/API keys | Denied to the technician role | Effective DocPerm/User permlevel configuration |

The missing files are listed in `docs/technician-access-validation.md`. Do not pretend this matrix is implemented before inspecting them. Avoid trusting client-side role checks, user-supplied assignees or filter parameters alone. Preserve existing rights and validate explicit negative cases on staging before changes to business permissions.

## GitHub and Frappe Cloud

Git access to this repository does not provide Frappe administrative authentication. Use the official Frappe Cloud UI and its GitHub integration to authorize the app source for the selected private bench; record the selected repository, branch/commit, installed apps and exact Frappe/ERPNext versions. Consult the official Cloud documentation at https://docs.frappe.io/cloud for the controls supported by the account/plan. No account-specific connection has been inspected or configured by these tools.

Do not add deploy keys, API secrets, site_config, backups or user records to Git. A GitHub merge is not evidence that a site deployed. Build the reviewed commit on compatible staging, inspect migration/restart results, test the real client/technician flow and controlled notifications, then obtain the production backup and explicit deployment approval described in `docs/deployment-review.md`. Keep the previous build and permission matrix for rollback. Do not deploy diagnostics solely to obtain production access.
