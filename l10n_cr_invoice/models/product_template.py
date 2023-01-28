# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

import requests
from datetime import datetime
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ProductElectronic(models.Model):
    _inherit = "product.template"

    @api.model
    def _default_code_type_id(self):
        code_type_id = self.env['code.type.product'].search(
            [('code', '=', '04')], limit=1)
        return code_type_id or False

    code_type_id = fields.Many2one("code.type.product", string="Tipo de Código", default=_default_code_type_id)

    tariff_head = fields.Char(string="Tasa de impuesto a la exportación",
                              help='Tasa de impuesto a aplicar para la exportación de facturas')


    cabys_code_id = fields.Many2one('product.cabys', string="Descripción CABYS")

    cabys_code = fields.Char(string="Código CABYS", help='Código CAByS de Ministerio de Hacienda')

    economic_activity_id = fields.Many2one("economic.activity", string="Actividad Económica",
                                           help='Código de Actividad Económica en Ministerio de Hacienda')

    non_tax_deductible = fields.Boolean(string='No deducible de impuestos', default=False,
                                        help='Indicates if this product is non-tax deductible')

    @api.onchange('cabys_code_id')
    def _cabys_code_changed(self):
        if self.cabys_code_id:
            if self.cabys_code_id.sale_ok:
                self.cabys_code = self.cabys_code_id.cabys_code
                self.taxes_id = self.cabys_code_id.tax_ids_s
            if self.cabys_code_id.purchase_ok:
                self.cabys_code = self.cabys_code_id.cabys_code
                self.supplier_taxes_id = self.cabys_code_id.tax_ids_p

        products = self.env['product.product'].sudo().search([('product_tmpl_id', '=', self.id)])

        for product in products:
            product.cabys_code_id = self.cabys_code_id.id
            if product.cabys_code_id.sale_ok:
                product.cabys_code = product.cabys_code_id.cabys_code
                product.taxes_id = product.cabys_code_id.tax_ids_s
            if product.cabys_code_id.purchase_ok:
                product.cabys_code = product.cabys_code_id.cabys_code
                product.supplier_taxes_id = product.cabys_code_id.tax_ids_p


class ProductCategory(models.Model):
    _inherit = "product.category"

    economic_activity_id = fields.Many2one("economic.activity", string="Actividad Económica",
                                           help='Código de Actividad Económica en Ministerio de Hacienda')

    cabys_code = fields.Char(string="Código CAByS", help='Código CAByS de Ministerio de Hacienda')
