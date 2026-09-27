import hashlib
import secrets
from datetime import timedelta
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EmployeeSelfServiceInvitation(models.Model):
    _name = "employee.self.service.invitation"
    _description = "ESS Activation and Reset Token"
    _order = "create_date desc"

    profile_id = fields.Many2one("employee.self.service.profile", required=True, ondelete="cascade", index=True)
    purpose = fields.Selection([("activation", "Activation"), ("reset", "Password reset")], required=True)
    token_hash = fields.Char(required=True, index=True, copy=False)
    expires_at = fields.Datetime(required=True, index=True)
    used_at = fields.Datetime(index=True)
    revoked_at = fields.Datetime(index=True)
    _sql_constraints = [("ess_invitation_token_unique", "unique(token_hash)", "Invalid duplicate invitation token.")]

    @api.model
    def issue(self, profile, purpose="activation"):
        config = self.env["employee.self.service.config"].sudo().for_company(profile.company_id)
        if not config:
            raise ValidationError(_("ESS is not enabled for this company."))
        self.sudo().search([("profile_id", "=", profile.id), ("purpose", "=", purpose), ("used_at", "=", False), ("revoked_at", "=", False)]).write({"revoked_at": fields.Datetime.now()})
        token = secrets.token_urlsafe(48)
        invitation = self.sudo().create({"profile_id": profile.id, "purpose": purpose, "token_hash": hashlib.sha256(token.encode()).hexdigest(), "expires_at": fields.Datetime.now() + timedelta(hours=config.invitation_validity_hours)})
        self.env["employee.self.service.audit.log"].sudo().create({"profile_id": profile.id, "event": "invited"})
        return invitation, token

    @api.model
    def consume(self, token, password):
        digest = hashlib.sha256((token or "").encode()).hexdigest()
        invitation = self.sudo().search([("token_hash", "=", digest), ("used_at", "=", False), ("revoked_at", "=", False), ("expires_at", ">", fields.Datetime.now())], limit=1)
        if not invitation:
            raise ValidationError(_("This link is invalid or has expired."))
        profile = invitation.profile_id
        profile.set_ess_password(password)
        invitation.write({"used_at": fields.Datetime.now()})
        profile.write({"state": "active", "enabled": True})
        self.env["employee.self.service.audit.log"].sudo().create({"profile_id": profile.id, "event": "activated" if invitation.purpose == "activation" else "password_reset"})
        return profile
