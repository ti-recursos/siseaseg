from odoo import fields, models, api, tools, _
from odoo.exceptions import UserError

class IrMailServer(models.Model):
    _inherit = "ir.mail_server"
    _description = 'Mail Server'

    type_bank = fields.Boolean(string="Issuer Recurring Charges", default=False)
    bank_receiver = fields.Char(string='Bank Receiver Mail', required=False, help="This email will receive recurring charges ")