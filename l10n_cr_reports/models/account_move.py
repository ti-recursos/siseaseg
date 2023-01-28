
import base64
import datetime
import json
import logging
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import pytz
from lxml import etree
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import get_lang

_logger = logging.getLogger(__name__)

class AccountInvoiceElectronicReport(models.Model):
    _inherit = "account.move"

    '''
        Campos para reporte de impuestos
    '''

    credit_fiscal = fields.Boolean(string='Crédito Fiscal')


    gasto_no_dedu = fields.Boolean(string='Gasto no deducible')
    
    tipo_gasto_no_dedu = fields.Selection(
        selection=[('locales', 'Locales'),
                   ('importados', 'Importados')],
        string="Bienes y servicios con o sin IVA soportado no acreditable", help="incluye compras de otros regímenes o no relacionados con la actividad",
        required=False)

    c_sin_imp = fields.Selection(
        selection=[
            ('hacienda', 'Autorizadas por la Dirección General de Hacienda'),
            ('tributacion', 'Autorizadas por la Dirección General de Tributación'),
            ('especial', 'Autorizadas por Ley especial')],
        string="Compras autorizadas sin impuesto (órdenes especiales)",
        required=False)
    

    csi_ley = fields.Char(string='N° Ley')
    csi_articulo = fields.Char(string='Artículo')
    csi_inciso = fields.Char(string='Insico(si aplica)')

    tipo_credit_fiscal = fields.Selection(
        selection=[('exenciones', 'Exenciones'),
                   ('no_sujecion', 'No sujeción')],
        string="Tipo Crédito Fiscal",
        required=False)

    
    # Campos para ventas
    venta_exentas = fields.Selection(string='Ventas Exentas (Art 8.)', selection=[
        ('0', 'Exportación de bienes'), 
        ('1', 'Exportación de servicios'),
        ('2', 'Venta local de bienes'), 
        ('3', 'Servicios prestados a nivel local'),
        ('4', 'Créditos para descuento de facturas y arrendamientos financieros u operativos en función financiera'), 
        ('5', 'Arrendamientos destinados a viviendas y accesorios, así como los lugares de culto religioso'),
        ('6', 'Arrendamientos utilizados por micro y pequeñas empresas'), 
        ('7', 'Suministro de energía eléctrica residencial no mayor a 280 KW/h'),
        ('8', 'Venta o entrega de agua residencial no mayor a 30m³'), 
        ('9', 'Autoconsumo de bienes y servicios sin aplicación de créditos total o parcial previamente'),
        ('10', 'Venta de sillas de ruedas y similares, equipo ortopédico, prótesis y equipo médico'), 
        ('11', 'Venta de bienes y servicios a instituciones públicas y privadas exentas'),
        ('12', 'Aranceles por matrículas y créditos de cursos en universidades públicas y servicios de educación privada autorizados por le MEP y/o CONESUP'), 
        ('13', 'Servicios de transporte terrestre de pasajeros y cabotaje de personas con concesión'),
        ('14', 'Venta, arrendamiento y leasing de autobuses y embarcaciones'), 
        ('15', 'Comisiones por el servicio de subasta ganadera y transacción de animales vivos en dichas subastas'),
        ('16', 'Venta, comercialización y matanza de animales vivos (semovientes) de industria pecuaria')
        ])
    
    venta_aut_sin_imp = fields.Selection(string='Ventas autorizadas sin impuesto (órdenes especiales y otros transitorios)', selection=[
        ('0', 'A clientes autorizados por la Dirección General de Hacienda'), 
        ('1', 'A clientes autorizados por la Dirección General de Tributación'),
        ('2', 'A clientes exonerados por ley especial'), 
        ('3', 'Venta de bienes y servicios relacionados a la canasta básica tributaria exentos el 1er año de la ley'),
        ('4', 'Servicios de ingeniería, arquitectura, topografía y construcción de obra civil'), 
        ('5', 'Servicios turísticos inscritos ante el Instituto Costarricense de Turismo')
        ])

    venta_no_sujeta = fields.Selection(string='Ventas no sujetas (Art.9)', selection=[
        ('0', 'Bienes y servicios a la Caja Costarricense de Seguro Social'), 
        ('1', 'Bienes y servicios a las corporaciones municipales'),
        ('2', 'Otras ventas no sujetas'),
        ])

    @api.onchange('partner_id')
    def _default_tipo_inversion(self):
        _logger.info('_default_tipo_inversion')

        for doc in self:
            if doc.move_type in ['in_invoice', 'in_refund']:
                doc.credit_fiscal = self.partner_id.credit_fiscal_compra
                doc.tipo_credit_fiscal = self.partner_id.tipo_credit_fiscal
            elif doc.move_type in ['out_invoice', 'out_refund']:
                doc.credit_fiscal = self.partner_id.credit_fiscal
                doc.tipo_credit_fiscal = self.partner_id.tipo_credit_fiscal

            if len(doc.line_ids) > 0:
                for line in doc.line_ids:
                    if line.move_type in ['in_invoice', 'in_refund']:
                        if line.product_id:
                            if line.move_id.partner_id.identification_id.code == '05':
                                if line.product_id.type == 'service':
                                    line.tipo_inversion = 'gasto_s_e'
                                else:
                                    line.tipo_inversion = 'compra_b_e'
                            else:
                                if line.product_id.type == 'service':
                                    line.tipo_inversion = 'gasto_s_l'
                                else:
                                    line.tipo_inversion = 'compra_b_l'
            if len(doc.invoice_line_ids) > 0:
                for line in doc.invoice_line_ids:
                    if line.move_type in ['in_invoice', 'in_refund']:
                        if line.product_id:
                            if line.move_id.partner_id.identification_id.code == '05':
                                if line.product_id.type == 'service':
                                    line.tipo_inversion = 'gasto_s_e'
                                else:
                                    line.tipo_inversion = 'compra_b_e'
                            else:
                                if line.product_id.type == 'service':
                                    line.tipo_inversion = 'gasto_s_l'
                                else:
                                    line.tipo_inversion = 'compra_b_l'

class InvoiceLineElectronicReport(models.Model):
    _inherit = "account.move.line"

    move_type = fields.Selection(related='move_id.move_type', store=True)

    @api.onchange('product_id')
    def _default_tipo_inversion(self):
        _logger.info('_default_tipo_inversion')
        for line in self:
            if line.move_id.partner_id:
                if line.move_type in ['in_invoice', 'in_refund']:
                    if line.product_id:
                        if line.move_id.partner_id.identification_id.code == '05':
                            if line.product_id.type == 'service':
                                line.tipo_inversion = 'gasto_s_e'
                            else:
                                line.tipo_inversion = 'compra_b_e'
                        else:
                            if line.product_id.type == 'service':
                                line.tipo_inversion = 'gasto_s_l'
                            else:
                                line.tipo_inversion = 'compra_b_l'

    tipo_inversion = fields.Selection(
        selection=[
                    ('compra_b_l', 'Compra de bienes-Local'),
                    ('bienes_c_l', 'Bienes de Capital-Local'),
                    ('gasto_s_l', 'Gastos por servicios-Local'),

                    ('compra_b_e', 'Compra de bienes-Exterior'),
                    ('bienes_c_e', 'Bienes de Capital-Exterior'),
                    ('gasto_s_e', 'Gastos por servicios-Exterior')],
        string="Tipo de Inversión",
        required=False)