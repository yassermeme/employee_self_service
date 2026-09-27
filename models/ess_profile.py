from datetime import timedelta
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from passlib.context import CryptContext

_PASSWORD_CONTEXT = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto")


class EmployeeSelfServiceProfile(models.Model):
    _name = "employee.self.service.profile"
    _description = "Employee Self Service Profile"
    _rec_name = "employee_id"
    _sql_constraints = [("ess_profile_employee_unique", "unique(employee_id)", "An employee can have only one ESS profile.")]

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="employee_id.company_id", store=True, readonly=True, index=True)
    employee_code = fields.Char(related="employee_id.barcode", readonly=False, store=True, index=True)
    work_email = fields.Char(related="employee_id.work_email", readonly=True, store=True, index=True)
    user_id = fields.Many2one(related="employee_id.user_id", readonly=True, store=True, index=True)
    enabled = fields.Boolean(default=True)
    authentication_mode = fields.Selection([("real", "Individual Odoo user"), ("shared", "Shared user"), ("both", "Both")], default="both", required=True)
    state = fields.Selection([("pending", "Pending activation"), ("active", "Active"), ("locked", "Locked"), ("disabled", "Disabled")], default="pending", required=True, index=True)
    password_hash = fields.Char(copy=False, groups="employee_self_service.group_ess_administrator")
    password_set = fields.Boolean(compute="_compute_password_set")
    failed_login_count = fields.Integer(default=0, copy=False)
    lockout_until = fields.Datetime(copy=False, index=True)
    last_successful_login = fields.Datetime(copy=False)
    last_password_change = fields.Datetime(copy=False)
    allowed_request_type_ids = fields.Many2many(
        "employee.self.service.request.type",
        "ess_profile_req_type_rel",
        "profile_id",
        "request_type_id",
        string="Allowed Financial Request Types",
    )

    @api.depends("password_hash")
    def _compute_password_set(self):
        for record in self:
            record.password_set = bool(record.password_hash)

    @api.constrains("employee_code", "work_email", "company_id")
    def _check_login_identifiers(self):
        for record in self:
            if record.employee_code and self.search_count([("id", "!=", record.id), ("company_id", "=", record.company_id.id), ("employee_code", "=", record.employee_code)]):
                raise ValidationError(_("Employee codes must be unique within a company."))
            if record.work_email and self.search_count([("id", "!=", record.id), ("company_id", "=", record.company_id.id), ("work_email", "=ilike", record.work_email)]):
                raise ValidationError(_("Work emails must be unique within a company."))

    def _assert_admin(self):
        if not self.env.user.has_group("employee_self_service.group_ess_administrator"):
            raise AccessError(_("Only ESS administrators may manage employee credentials."))

    def set_ess_password(self, password):
        self.ensure_one()
        if not isinstance(password, str):
            raise ValidationError(_("Invalid password."))
        config = self.env["employee.self.service.config"].for_company(self.company_id)
        if not config or len(password) < config.password_min_length:
            raise ValidationError(_("The password does not meet the configured password policy."))
        self.with_context(ess_password_write=True).write({"password_hash": _PASSWORD_CONTEXT.hash(password), "last_password_change": fields.Datetime.now(), "failed_login_count": 0, "lockout_until": False})
        self.env["employee.self.service.session"].sudo().revoke_for_profile(self, "password_reset")

    def verify_ess_password(self, password):
        self.ensure_one()
        return bool(self.password_hash and _PASSWORD_CONTEXT.verify(password or "", self.password_hash))

    def action_enable(self):
        self._assert_admin(); self.write({"enabled": True, "state": "pending"})

    def action_disable(self):
        self._assert_admin(); self.write({"enabled": False, "state": "disabled"}); self.env["employee.self.service.session"].sudo().revoke_for_profile(self, "session_revoked")

    def action_unlock(self):
        self._assert_admin(); self.write({"state": "active" if self.password_hash else "pending", "failed_login_count": 0, "lockout_until": False})

    def action_revoke_sessions(self):
        self._assert_admin(); self.env["employee.self.service.session"].sudo().revoke_for_profile(self, "session_revoked")
