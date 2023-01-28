# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_method = fields.Selection(
        selection=[('internal', 'Interno'),
                   ('cisa', 'CISA')],
        string="Método de Pago",
        required=False, help='Inidica el medio por el que se realizó el pago')

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)
        return res