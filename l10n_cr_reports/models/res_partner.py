# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, Warning


import logging
_logger = logging.getLogger(__name__)


class PartnerElectronicReport(models.Model):
    _inherit = "res.partner"

    is_extra_fronterizo = fields.Boolean(string='Extra Fronterizo')
    is_zona_franca = fields.Boolean(string='Zona Franca')
    
    '''
        Campos para reporte de impuestos
    '''

    credit_fiscal = fields.Boolean(string='Crédito Fiscal Venta')
    credit_fiscal_compra = fields.Boolean(string='Crédito Fiscal Compra')

    tipo_credit_fiscal = fields.Selection(
        selection=[('exenciones', 'Exenciones'),
                   ('no_sujecion', 'No sujeción')],
        string="Tipo Crédito Fiscal",
        required=False)

    @api.onchange('credit_fiscal')
    def _credit_fiscal_changed(self):
        for move in self:
            if move.credit_fiscal == True:
                move.tipo_credit_fiscal = False
            if move.credit_fiscal == False:
                move.tipo_credit_fiscal = False
    
    @api.onchange('credit_fiscal_compra')
    def _credit_fiscal_changed(self):
        for move in self:
            if move.credit_fiscal == True:
                move.tipo_credit_fiscal = False
            if move.credit_fiscal == False:
                move.tipo_credit_fiscal = False