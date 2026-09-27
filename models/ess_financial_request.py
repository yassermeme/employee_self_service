from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class EmployeeSelfServiceRequestType(models.Model):
    _name = "employee.self.service.request.type"
    _description = "ESS Financial Request Type"
    _order = "company_id, name"

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    minimum_amount = fields.Monetary(default=0)
    maximum_amount = fields.Monetary(default=0, help="Zero means no maximum.")
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    requires_document = fields.Boolean()
    _sql_constraints = [("ess_request_type_amount", "CHECK(maximum_amount >= 0 AND minimum_amount >= 0)", "Amounts cannot be negative.")]


class EmployeeSelfServiceFinancialRequest(models.Model):
    _name = "employee.self.service.financial.request"
    _description = "ESS Financial Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(default="New", readonly=True, copy=False)
    profile_id = fields.Many2one("employee.self.service.profile", required=True, readonly=True, ondelete="restrict", index=True)
    employee_id = fields.Many2one(related="profile_id.employee_id", store=True, readonly=True, index=True)
    company_id = fields.Many2one(related="profile_id.company_id", store=True, readonly=True, index=True)
    request_type_id = fields.Many2one("employee.self.service.request.type", required=True, ondelete="restrict")
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    reason = fields.Text(required=True)
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("review", "Under review"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("paid", "Paid")], default="draft", required=True, tracking=True, index=True)
    approval_comment = fields.Text(readonly=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)

    @api.constrains("amount", "request_type_id")
    def _check_amount(self):
        for record in self:
            if record.amount <= 0 or record.amount < record.request_type_id.minimum_amount or (record.request_type_id.maximum_amount and record.amount > record.request_type_id.maximum_amount):
                raise ValidationError(_("The requested amount is outside the permitted range."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "profile_id" not in vals or "state" in vals:
                raise AccessError(_("Financial request creation must be performed through ESS."))
        return super().create(vals_list)

    def action_submit(self):
        for record in self:
            if record.state != "draft": raise ValidationError(_("Only draft requests can be submitted."))
            record.write({"state": "submitted"})
            self.env["employee.self.service.audit.log"].sudo().create({"profile_id": record.profile_id.id, "event": "financial_submitted"})

    def action_cancel(self):
        if any(record.state not in ("draft", "submitted") for record in self): raise ValidationError(_("Only draft or submitted requests can be cancelled."))
        self.write({"state": "cancelled"})
