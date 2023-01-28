

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

from odoo.tests.common import Form

class AccountInvoiceElectronic(models.Model):
    _inherit = "account.move"
    _description = "Account"

    periodo_sub = fields.Date(string="Periodo SUB", required=False)

    def action_post(self):
        for inv in self:
            super(AccountInvoiceElectronic, inv).action_post()
            if not inv.periodo_sub and inv.invoice_date:
                inv.periodo_sub = inv.invoice_date