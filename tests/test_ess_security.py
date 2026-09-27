from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestEssSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.employee_a = cls.env["hr.employee"].create({"name": "ESS A", "company_id": cls.company.id, "barcode": "ESS-A", "work_email": "a@example.test"})
        cls.employee_b = cls.env["hr.employee"].create({"name": "ESS B", "company_id": cls.company.id, "barcode": "ESS-B", "work_email": "b@example.test"})
        cls.profile_a = cls.env["fi.ess.profile"].create({"employee_id": cls.employee_a.id, "state": "active"})
        cls.profile_b = cls.env["fi.ess.profile"].create({"employee_id": cls.employee_b.id, "state": "active"})
        cls.request_type = cls.env["fi.ess.request.type"].create({"name": "Advance", "company_id": cls.company.id})

    def test_profile_is_unique_per_employee(self):
        with self.assertRaises(Exception):
            self.env["fi.ess.profile"].create({"employee_id": self.employee_a.id})

    def test_session_token_is_not_stored_in_plaintext(self):
        user = self.env.user
        token = self.env["fi.ess.session"].create_for_request(self.profile_a, user, "test-session-a", "real")
        session = self.env["fi.ess.session"].validate_for_request(token, user, "test-session-a")
        self.assertEqual(session.profile_id, self.profile_a)
        self.assertNotEqual(session.token_hash, token)
        self.assertFalse(self.env["fi.ess.session"].validate_for_request(token, user, "other-session"))

    def test_financial_request_requires_server_selected_profile(self):
        with self.assertRaises(AccessError):
            self.env["fi.ess.financial.request"].create({"request_type_id": self.request_type.id, "amount": 100, "reason": "forged"})
