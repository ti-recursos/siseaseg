# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    expense_product_id = fields.Many2one(
        'product.product',
        company_dependent=True,
        string=_("Producto predeterminado para gastos al cargar datos desde XML"),
        help=_("El producto predeterminado utilizado al cargar la factura digital costarricense"))

    expense_account_id = fields.Many2one(
        'account.account',
        company_dependent=True,
        string=_("Cuenta de gastos predeterminada al cargar datos desde XML"),
        help=_("La cuenta de gastos utilizada al cargar la factura digital costarricense"))

    expense_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        company_dependent=True,
        string=_("Cuenta analítica predeterminada para gastos al cargar datos desde XML"),
        help=_("La cuenta analítica utilizada al cargar la factura digital costarricense"))

    load_lines = fields.Boolean(
        string=_('Indica si se deben cargar líneas de factura al cargar una factura digital costarricense'),
        default=True
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(
            expense_account_id=int(get_param('expense_account_id')),
            load_lines=get_param('load_lines'),
            expense_product_id=int(get_param('expense_product_id')),
            expense_analytic_account_id=int(get_param('expense_analytic_account_id')),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        set_param('expense_account_id', self.expense_account_id.id)
        set_param('load_lines', self.load_lines)
        set_param('expense_product_id', self.expense_product_id.id)
        set_param('expense_analytic_account_id', self.expense_analytic_account_id.id)
