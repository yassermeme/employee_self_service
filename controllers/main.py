from odoo import _, fields, http
from odoo.http import request
from odoo.exceptions import ValidationError
from werkzeug.exceptions import Forbidden


class FiEssController(http.Controller):
    def _session_id(self):
        return getattr(request.session, "sid", None)

    def _audit(self, profile, event):
        request.env["fi.ess.audit.log"].sudo().create({"profile_id": profile.id, "actor_user_id": request.env.user.id, "event": event, "remote_addr": request.httprequest.remote_addr})

    def _real_profile(self, user):
        profiles = request.env["fi.ess.profile"].sudo().search([("user_id", "=", user.id), ("enabled", "=", True), ("state", "=", "active")])
        if len(profiles) != 1:
            return request.env["fi.ess.profile"]
        profile = profiles
        config = request.env["fi.ess.config"].sudo().for_company(profile.company_id)
        return profile if config and config.authentication_mode in ("real", "both") else request.env["fi.ess.profile"]

    def _context(self):
        user = request.env.user
        if not user or user._is_public():
            raise Forbidden()
        raw_token = request.session.get("fi_ess_token")
        session = request.env["fi.ess.session"].validate_for_request(raw_token, user, self._session_id())
        if session:
            return session.profile_id
        profile = self._real_profile(user)
        if not profile:
            raise Forbidden()
        token = request.env["fi.ess.session"].create_for_request(profile, user, self._session_id(), "real")
        request.session["fi_ess_token"] = token
        return profile

    @http.route("/ess", type="http", auth="user", methods=["GET"], csrf=False)
    def dashboard(self, **_kwargs):
        profile = self._context()
        financial_count = request.env["fi.ess.financial.request"].sudo().search_count([("profile_id", "=", profile.id), ("state", "in", ["submitted", "review"])])
        values = {"profile": profile, "financial_count": financial_count, "features": request.env["fi.ess.config"].sudo().for_company(profile.company_id)}
        return request.render("fi_employee_self_service.ess_dashboard", values)

    @http.route("/ess/shared/login", type="http", auth="user", methods=["GET", "POST"], csrf=True)
    def shared_login(self, identifier=None, password=None, **_kwargs):
        user = request.env.user
        if user._is_public():
            raise Forbidden()
        configs = request.env["fi.ess.config"].sudo().search([("enabled", "=", True), ("shared_user_id", "=", user.id), ("authentication_mode", "in", ["shared", "both"])])
        if not configs:
            raise Forbidden()
        if request.httprequest.method == "GET":
            return request.render("fi_employee_self_service.ess_shared_login", {"error": False})
        profile = request.env["fi.ess.profile"].sudo().search([("company_id", "in", configs.company_id.ids), ("enabled", "=", True), ("state", "in", ["active", "locked"]), "|", ("employee_code", "=", identifier), ("work_email", "=ilike", identifier)], limit=1)
        # Generic error avoids account enumeration.  Lockout is checked before verification.
        if not profile or profile.state == "locked" or (profile.lockout_until and profile.lockout_until > fields.Datetime.now()):
            return request.render("fi_employee_self_service.ess_shared_login", {"error": _("Invalid credentials or account unavailable.")})
        if not profile.verify_ess_password(password):
            config = request.env["fi.ess.config"].sudo().for_company(profile.company_id)
            profile.flush_recordset(["failed_login_count"])
            request.env.cr.execute("SELECT id FROM fi_ess_profile WHERE id = %s FOR UPDATE", [profile.id])
            profile.invalidate_recordset(["failed_login_count"])
            attempts = profile.failed_login_count + 1
            values = {"failed_login_count": attempts}
            event = "login_failed"
            if attempts >= config.max_failed_logins:
                values.update({"state": "locked", "lockout_until": fields.Datetime.now() + __import__("datetime").timedelta(minutes=config.lockout_minutes)})
                event = "locked"
            profile.write(values); self._audit(profile, event)
            return request.render("fi_employee_self_service.ess_shared_login", {"error": _("Invalid credentials or account unavailable.")})
        request.session.pop("fi_ess_token", None)
        token = request.env["fi.ess.session"].create_for_request(profile, user, self._session_id(), "shared")
        request.session["fi_ess_token"] = token
        profile.write({"failed_login_count": 0, "lockout_until": False, "state": "active", "last_successful_login": fields.Datetime.now()})
        self._audit(profile, "login")
        return request.redirect("/ess")

    @http.route("/ess/logout", type="http", auth="user", methods=["POST"], csrf=True)
    def logout(self, **_kwargs):
        raw_token = request.session.pop("fi_ess_token", None)
        session = request.env["fi.ess.session"].validate_for_request(raw_token, request.env.user, self._session_id())
        if session:
            session.sudo().write({"revoked_at": fields.Datetime.now()}); self._audit(session.profile_id, "logout")
        return request.redirect("/web")

    @http.route("/ess/financial", type="http", auth="user", methods=["GET"], csrf=False)
    def financial(self, **_kwargs):
        profile = self._context()
        records = request.env["fi.ess.financial.request"].sudo().search([("profile_id", "=", profile.id)])
        return request.render("fi_employee_self_service.ess_financial_list", {"records": records, "profile": profile})

    @http.route("/ess/financial/create", type="http", auth="user", methods=["POST"], csrf=True)
    def financial_create(self, request_type_id=None, amount=None, reason=None, **_kwargs):
        profile = self._context(); config = request.env["fi.ess.config"].sudo().for_company(profile.company_id)
        if not config.allow_financial_requests:
            raise Forbidden()
        request_type = request.env["fi.ess.request.type"].sudo().browse(int(request_type_id or 0)).exists()
        if not request_type or request_type.company_id != profile.company_id or not request_type.active or (profile.allowed_request_type_ids and request_type not in profile.allowed_request_type_ids):
            raise Forbidden()
        record = request.env["fi.ess.financial.request"].sudo().create({"profile_id": profile.id, "request_type_id": request_type.id, "amount": float(amount or 0), "reason": reason or ""})
        record.action_submit()
        return request.redirect("/ess/financial")
