from odoo import fields, models


class FiEssAuditLog(models.Model):
    _name = "fi.ess.audit.log"
    _description = "ESS Security Audit Log"
    _order = "create_date desc, id desc"
    _rec_name = "event"

    profile_id = fields.Many2one("fi.ess.profile", ondelete="set null", index=True)
    company_id = fields.Many2one(related="profile_id.company_id", store=True, index=True)
    actor_user_id = fields.Many2one("res.users", ondelete="set null")
    event = fields.Selection([
        ("login", "Login"), ("login_failed", "Login failed"), ("locked", "Account locked"),
        ("logout", "Logout"), ("session_revoked", "Session revoked"), ("invited", "Invitation issued"),
        ("activated", "Account activated"), ("password_reset", "Password reset"),
        ("financial_submitted", "Financial request submitted"), ("attendance", "Attendance action"),
    ], required=True, index=True)
    detail = fields.Char()
    remote_addr = fields.Char(string="Remote Address")
