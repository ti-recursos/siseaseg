from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class IvaCodeType(models.Model):
    _inherit = "account.tax"

    tax_code = fields.Char(string="Tax Code", required=False, )
    iva_tax_desc = fields.Char(string="VAT Tax Rate", default='N/A', required=False, )
    iva_tax_code = fields.Char(string="VAT Rate Code", default='N/A', required=False, )
    has_exoneration = fields.Boolean(string="Has Exoneration", required=False)
    percentage_exoneration = fields.Float(string="Percentage of VAT Exoneration", required=False)
    tax_root = fields.Many2one("account.tax", string="Parent Tax", required=False, )
    non_tax_deductible = fields.Boolean(string='Indicates if this tax is no deductible for Rent and VAT',)

    @api.onchange('percentage_exoneration')
    def _onchange_percentage_exoneration(self):
        self.tax_compute_exoneration()

    @api.onchange('tax_root')
    def _onchange_tax_root(self):
        self.amount = self.tax_root.amount
        self.tax_compute_exoneration()

    def tax_compute_exoneration(self):
        if self.percentage_exoneration:
            if self.tax_root:
                self.amount = self.tax_root.amount
                percent = self.amount - self.percentage_exoneration
                self.amount = percent



