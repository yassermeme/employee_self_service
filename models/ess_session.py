import hashlib
import secrets
from datetime import timedelta
from odoo import api, fields, models


class EmployeeSelfServiceSession(models.Model):
    _name = "employee.self.service.session"
    _description = "Server-side ESS Session"
    _rec_name = "profile_id"
    _order = "create_date desc"

    profile_id = fields.Many2one("employee.self.service.profile", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    token_hash = fields.Char(required=True, index=True, copy=False)
    odoo_session_id_hash = fields.Char(required=True, index=True, copy=False)
    expires_at = fields.Datetime(required=True, index=True)
    revoked_at = fields.Datetime(index=True)
    last_seen_at = fields.Datetime()
    auth_method = fields.Selection([("real", "Individual Odoo user"), ("shared", "Shared Odoo user")], required=True)
    _sql_constraints = [("ess_session_token_unique", "unique(token_hash)", "Invalid duplicate session token.")]

    @staticmethod
    def _digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    @api.model
    def create_for_request(self, profile, user, odoo_session_id, auth_method):
        config = self.env["employee.self.service.config"].sudo().for_company(profile.company_id)
        raw_token = secrets.token_urlsafe(48)
        now = fields.Datetime.now()
        self.sudo().create({
            "profile_id": profile.id, "user_id": user.id, "token_hash": self._digest(raw_token),
            "odoo_session_id_hash": self._digest(odoo_session_id), "auth_method": auth_method,
            "expires_at": now + timedelta(minutes=config.session_duration_minutes), "last_seen_at": now,
        })
        return raw_token

    @api.model
    def validate_for_request(self, raw_token, user, odoo_session_id):
        if not raw_token or not user or not odoo_session_id:
            return self.browse()
        now = fields.Datetime.now()
        session = self.sudo().search([
            ("token_hash", "=", self._digest(raw_token)), ("user_id", "=", user.id),
            ("odoo_session_id_hash", "=", self._digest(odoo_session_id)), ("revoked_at", "=", False),
            ("expires_at", ">", now), ("profile_id.enabled", "=", True), ("profile_id.state", "=", "active"),
        ], limit=1)
        if session:
            session.write({"last_seen_at": now})
        return session

    @api.model
    def revoke_for_profile(self, profile, event="session_revoked"):
        active = self.sudo().search([("profile_id", "=", profile.id), ("revoked_at", "=", False)])
        if active:
            active.write({"revoked_at": fields.Datetime.now()})
            self.env["employee.self.service.audit.log"].sudo().create([{"profile_id": profile.id, "event": event} for _item in active])

    @api.autovacuum
    def _gc_expired_sessions(self):
        self.sudo().search([("expires_at", "<", fields.Datetime.now() - timedelta(days=7))]).unlink()
