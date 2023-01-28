# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_method = fields.Selection(selection_add=[('automatic_charge', 'Cargo Automático')])

    contract = fields.Char(string="Contrato", required=False)

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)
        return res