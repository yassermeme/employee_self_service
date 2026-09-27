from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EmployeeSelfServiceConfig(models.Model):
    _name = "employee.self.service.config"
    _description = "Employee Self Service Configuration"
    _rec_name = "company_id"
    _sql_constraints = [
        ("ess_config_company_unique", "unique(company_id)", "Only one ESS configuration is allowed per company."),
    ]

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    enabled = fields.Boolean(default=True)
    authentication_mode = fields.Selection([
        ("real", "Individual Odoo users"), ("shared", "Shared Odoo user"), ("both", "Both"),
    ], required=True, default="both")
    shared_user_id = fields.Many2one("res.users", string="Shared Odoo User", ondelete="restrict")
    session_duration_minutes = fields.Integer(default=30, required=True)
    max_failed_logins = fields.Integer(default=5, required=True)
    lockout_minutes = fields.Integer(default=15, required=True)
    invitation_validity_hours = fields.Integer(default=24, required=True)
    password_min_length = fields.Integer(default=12, required=True)
    password_expiration_days = fields.Integer(default=0)
    login_identifier = fields.Selection([("code", "Employee code"), ("email", "Work email"), ("either", "Either")], default="either", required=True)
    allow_payslips = fields.Boolean(default=True)
    allow_leave = fields.Boolean(default=True)
    allow_attendance_view = fields.Boolean(default=True)
    allow_attendance_action = fields.Boolean(default=False)
    allow_financial_requests = fields.Boolean(default=True)

    @api.constrains("authentication_mode", "shared_user_id", "session_duration_minutes", "max_failed_logins", "lockout_minutes", "invitation_validity_hours", "password_min_length", "password_expiration_days")
    def _check_security_values(self):
        for record in self:
            if record.authentication_mode in ("shared", "both") and not record.shared_user_id:
                raise ValidationError(_("A shared Odoo user is required when shared authentication is enabled."))
            if record.shared_user_id and record.shared_user_id.company_id and record.shared_user_id.company_id != record.company_id:
                raise ValidationError(_("The shared user must belong to the configured company."))
            if record.shared_user_id and record.shared_user_id.has_group("hr.group_hr_user"):
                raise ValidationError(_("A shared ESS user cannot have Human Resources user access."))
            if record.session_duration_minutes < 1 or record.max_failed_logins < 1 or record.lockout_minutes < 1:
                raise ValidationError(_("Session duration, login limit, and lockout duration must be positive."))
            if record.invitation_validity_hours < 1 or record.password_min_length < 8 or record.password_expiration_days < 0:
                raise ValidationError(_("Invitation validity must be positive and passwords must be at least 8 characters."))

    @api.model
    def for_company(self, company):
        return self.search([("company_id", "=", company.id), ("enabled", "=", True)], limit=1)
