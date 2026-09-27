# Employee Self Service (ESS) (Odoo 19)

## Installation

Install this addon in an Odoo 19 addons path and update the Apps list.  Its required
modules are `hr`, `mail`, and `web`. It intentionally does **not** depend on Payroll,
Time Off, or Attendances because those capabilities differ by edition; integrations
must be enabled only after confirming their installed Odoo 19 model and report APIs.

## Configuration and onboarding

1. Give an HR administrator **ESS Administrator**.
2. Create one `ESS Configuration` per company and select individual, shared, or both
   authentication methods.
3. Create one ESS profile per employee. Set a unique employee barcode/code and work
   email, enable it, and use a time-limited activation/reset invitation to establish a
   password.
4. For shared mode, configure a dedicated user that has no HR User access. Do not give
   it HR, Payroll, Time Off, or Attendance groups.

## Security design

All employee-facing routes resolve the employee on the server. A shared-mode login
creates a 48-byte random secret held only in Odoo's server-side session and a hashed
record in `employee.self.service.session`. The record is bound to the authenticated Odoo user and the
Odoo session identifier, expires, and can be revoked. No route accepts an employee ID
as its authority. Financial records are always queried by the resolved profile ID.

ESS passwords use salted PBKDF2-SHA512 hashes; reset/activation tokens are random,
hashed at rest, one-time, and expiring. Failed logins use a row lock before changing
attempt counts. Audit records deliberately exclude secrets.

## Current integrations and limitations

The core ESS identity, session, financial-request workflow, administrator views, and
shared-user dashboard are implemented. Payroll, Time Off, Attendance, attachment, and
report integrations are intentionally not declared as complete: this repository has no
Odoo runtime or installed optional HR modules to inspect or test. Do not enable a
shared account with access to those modules until module-specific route and report
ownership checks have been added and tested against the installed Odoo edition.

## Testing

Run Odoo module tests on a disposable Odoo 19 database:

```bash
odoo-bin -d ess_test -i employee_self_service --test-enable --stop-after-init
odoo-bin -d ess_test -u employee_self_service --test-enable --stop-after-init
```

The supplied test suite focuses on the server-side session and cross-profile financial
isolation. Add edition-specific payroll/leave/attendance/report tests before enabling
those optional services.
