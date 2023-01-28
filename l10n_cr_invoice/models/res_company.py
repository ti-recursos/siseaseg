# -*- coding: utf-8 -*-

import logging
import phonenumbers

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

# Validar Fecha de expiración de Llave Criptográfica
import base64
from datetime import datetime

try:
    from OpenSSL import crypto
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
except(ImportError, IOError) as err:
    logging.info(err)

from . import api_facturae

import requests
import json

_logger = logging.getLogger(__name__)

#FORM for resequence
from odoo.tests.common import Form
_TIPOS_CONFIRMACION = (
    # Provides listing of types of comprobante confirmations
    ('CCE_sequence_id', 'account.invoice.supplier.accept.',
     'Supplier invoice acceptance sequence'),
    ('CPCE_sequence_id', 'account.invoice.supplier.partial.',
     'Supplier invoice partial acceptance sequence'),
    ('RCE_sequence_id', 'account.invoice.supplier.reject.',
     'Supplier invoice rejection sequence'),
    ('FEC_sequence_id', 'account.invoice.supplier.reject.',
     'Supplier electronic purchase invoice sequence'),
)


class CompanyElectronic(models.Model):
    _name = 'res.company'
    _inherit = ['res.company', 'mail.thread', ]

    commercial_name = fields.Char(string="Commercial Name", required=False, )
    activity_id = fields.Many2one("economic.activity", string="Default economic activity", required=False,
                                  context={'active_test': False})
    signature = fields.Binary(string="Llave Criptográfica", )
    identification_id = fields.Many2one("identification.type", string="Id Type", required=False)
    frm_ws_identificador = fields.Char(string="Electronic invoice user", required=False)
    frm_ws_password = fields.Char(string="Electronic invoice password", required=False)

    frm_ws_ambiente = fields.Selection(selection=[('disabled', 'Deshabilitado'),
                                                  ('api-stag', 'Pruebas'),
                                                  ('api-prod', 'Producción')],
                                       string="Environment",
                                       required=True,
                                       default='disabled',
                                       help='Es el ambiente en al cual se le está actualizando el certificado. Para el ambiente '
                                            'de calidad (stag), para el ambiente de producción (prod). Requerido.')

    frm_pin = fields.Char(string="Pin",
                          required=False,
                          help='Es el pin correspondiente al certificado. Requerido')

    frm_ws_expiracion = fields.Date(string='Fecha de Vencimiento de Llave Criptográfica', readonly=True, )

    sucursal_MR = fields.Integer(string="Sucursal para secuencias de MRs",
                                 required=False,
                                 default="1")

    terminal_MR = fields.Integer(string="Terminal para secuencias de MRs",
                                 required=False,
                                 default="1")

    secuencia_interna = fields.Boolean(string='Secuencia diferente a Factura Electrónica?')

    CCE_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Secuencia Aceptación',
        help='Secuencia de confirmacion de aceptación de comprobante electrónico. Dejar en blanco '
             'y el sistema automaticamente se lo creará.',
        readonly=False, copy=False,
    )

    CPCE_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Secuencia Parcial',
        help='Secuencia de confirmación de aceptación parcial de comprobante electrónico. Dejar '
             'en blanco y el sistema automáticamente se lo creará.',
        readonly=False, copy=False,
    )
    RCE_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Secuencia Rechazo',
        help='Secuencia de confirmación de rechazo de comprobante electrónico. Dejar '
             'en blanco y el sistema automáticamente se lo creará.',
        readonly=False, copy=False,
    )
    FEC_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Secuencia de Facturas Electrónicas de Compra',
        readonly=False, copy=False,
    )

    # Se agrega campos para consultar información de código CAByS colocado
    ultima_respuesta_cabys = fields.Text(string="Última Respuesta de API CAByS",
                                         help="Última Respuesta de API CAByS, esto permite depurar errores en caso de existir")
    url_base_cabys = fields.Char(string="URL Base CAByS", required=False, help="URL Base del END POINT CAByS",
                                 default="https://api.hacienda.go.cr/fe/cabys?")

    # Se agrega campos para consultar información de exoneraciones
    ultima_respuesta_exo = fields.Text(string="Última Respuesta de API EXONET",
                                         help="Última Respuesta de API EXONET, esto permite depurar errores en caso de existir")
    url_base_exo = fields.Char(string="URL Base CAByS", required=False, help="URL Base del END POINT EXONET",
                                 default="https://api.hacienda.go.cr/fe/ex?")

    '''
        Para controlar facturación de la compañía 
    '''

    partner_key = fields.Char(string="Llave de Cliente", required=False, readonly=False)

    n_fe = fields.Integer(string="Factura Electrónica", required=False, readonly=False)
    n_fee = fields.Integer(string="Factura Electrónica de Exportación", required=False, readonly=False)
    n_te = fields.Integer(string="Tiquete Electrónico", required=False, readonly=False)
    n_nc = fields.Integer(string="Nota de Crédito", required=False, readonly=False)
    n_nd = fields.Integer(string="Nota de Débito", required=False, readonly=False)
    n_cce = fields.Integer(string="MR Aceptación", required=False, readonly=False)
    n_cpce = fields.Integer(string="MR Aceptación Parcial", required=False, readonly=False)
    n_rce = fields.Integer(string="MR Rechazo", required=False, readonly=False)
    n_fec = fields.Integer(string="Factura Electrónica de Compra", required=False, readonly=False)

    state_fe = fields.Boolean(string='Estado Facturación Electrónica', readonly=True)
    url_tir = fields.Char(string="URL Validador FE", required=False, help="URL Base del END POINT TI Recursos",
                          default="https://tirecursos.odoo.com/v1/facturacion/")

    @api.onchange('mobile')
    def _onchange_mobile(self):
        if self.mobile:
            mobile = phonenumbers.parse(self.mobile, self.country_id.code)
            valid = phonenumbers.is_valid_number(mobile)
            if not valid:
                alert = {
                    'title': 'Atención',
                    'message': 'Número de teléfono inválido'
                }
                return {'value': {'mobile': ''}, 'warning': alert}

    @api.onchange('phone')
    def _onchange_phone(self):
        if self.phone:
            phone = phonenumbers.parse(self.phone, self.country_id.code)
            valid = phonenumbers.is_valid_number(phone)
            if not valid:
                alert = {
                    'title': 'Atención',
                    'message': 'Número de teléfono inválido'
                }
                return {'value': {'phone': ''}, 'warning': alert}        
                
    @api.model
    def create(self, vals):
        """ Try to automatically add the Comprobante Confirmation sequence to the company.
            It will attempt to create and assign before storing. The sequence that is
            created will be coded with the following syntax:
                account.invoice.supplier.<tipo>.<company_name>
            where tipo is: accept, partial or reject, and company_name is either the first word
            of the name or commercial name.
        """
        new_comp_id = super(CompanyElectronic, self).create(vals)
        # new_comp = self.browse(new_comp_id)
        new_comp_id.try_create_configuration_sequences()

        # Encargado de crear las secuencias de los documentos electrónicos
        new_comp_id.try_create_sequences()

        # Encargado de crear los impuestos de los documentos electrónicos
        new_comp_id.try_create_taxes()
        return new_comp_id  # new_comp.id

    def try_create_configuration_sequences(self):
        """ Try to automatically add the Comprobante Confirmation sequence to the company.
            It will first check if sequence already exists before attempt to create. The s
            equence is coded with the following syntax:
                account.invoice.supplier.<tipo>.<company_name>
            where tipo is: accept, partial or reject, and company_name is either the first word
            of the name or commercial name.
        """
        company_subname = self.commercial_name
        if not company_subname:
            company_subname = getattr(self, 'name')
        company_subname = company_subname.split(' ')[0].lower()
        ir_sequence = self.env['ir.sequence']
        to_write = {}
        for field, seq_code, seq_name in _TIPOS_CONFIRMACION:
            if not getattr(self, field, None):
                seq_code += company_subname
                seq = self.env.ref(seq_code, raise_if_not_found=False) or ir_sequence.create({
                    'name': seq_name,
                    'code': seq_code,
                    'implementation': 'standard',
                    'padding': 10,
                    'use_date_range': False,
                    'company_id': getattr(self, 'id'),
                })
                to_write[field] = seq.id

        if to_write:
            self.write(to_write)

    def try_create_sequences(self):
        '''
            Se encarga de crear todas las secuencias respectivas a Factura Electrónica
        '''

        # Secuencia Factura Electrónica
        self.env['ir.sequence'].create({
            'name': 'Secuencia de Factura Electrónica',
            'code': 'sequece.FE',
            'prefix': '',
            'padding': 10,
            'company_id': self.id
        })
        # Secuencia de Nota Débito Electrónica
        self.env['ir.sequence'].create({
            'name': 'Secuencia de Nota Débito Electrónica',
            'code': 'sequece.ND',
            'prefix': '',
            'padding': 10,
            'company_id': self.id
        })

        ##### Revisar evento de busqueda de cabys


        # Secuencia de Nota Crédito Electrónica
        self.env['ir.sequence'].create({
            'name': 'Secuencia de Nota Crédito Electrónica',
            'code': 'sequece.NC',
            'prefix': '',
            'padding': 10,
            'company_id': self.id
        })
        # Secuencia de Tiquete Electrónico
        self.env['ir.sequence'].create({
            'name': 'Secuencia de Tiquete Electrónico',
            'code': 'sequece.TE',
            'prefix': '',
            'padding': 10,
            'company_id': self.id
        })
        # Secuencia de Factura Electrónica de Exportación
        self.env['ir.sequence'].create({
            'name': 'Secuencia de Factura Electrónica de Exportación',
            'code': 'sequece.FEE',
            'prefix': '',
            'padding': 10,
            'company_id': self.id
        })
        # Secuencia de Factura Electrónica de Compra
        self.env['ir.sequence'].create({
            'name': 'Secuencia de Factura Electrónica de Compra',
            'code': 'sequece.FEC',
            'prefix': '',
            'padding': 10,
            'company_id': self.id
        })


    def try_create_taxes(self):

        # IVA 0%
        self.env['account.tax'].create({
            'name': 'Secuencia de Factura Electrónica de Compra',
            'tax_code': '01',
            'type_tax_use': 'sale',
            'padding': 10,
            'company_id': self.id
        })

    def test_get_token(self):
        token_m_h = api_facturae.get_token_hacienda(
            self.env.user, self.frm_ws_ambiente)
        if token_m_h:
            _logger.info('E-INV CR - I got the token')

        certificate = crypto.load_pkcs12(base64.b64decode(self.signature), self.frm_pin)
        pem_data = crypto.dump_certificate(crypto.FILETYPE_PEM, certificate.get_certificate())
        cert = x509.load_pem_x509_certificate(pem_data, default_backend())
        self.frm_ws_expiracion = str(cert.not_valid_after)
        return

    def update_key(self):
        _logger.info('E-INV CR - Check partner key')

        try:
            parametros = {'r': 'Status'}
            response = requests.get(str(self.url_tir), params=parametros)

            if 200 <= response.status_code <= 299:
                response_json = response.json()
                codigo = response_json.get('Codigo')
                if codigo == '00':
                    params = {
                        'r': 'Consulta',
                        'id': str(self.vat),
                        'key': str(self.partner_key),
                    }
                    resp = requests.get(str(self.url_tir), params=params)
                    if 200 <= resp.status_code <= 299:
                        json_obj = resp.json()
                        status = json_obj.get('Codigo')
                        message_description = ''
                        if status == "08":
                            self.state_fe = True
                            message_description += '<p>El servicio de factura electrónica se encuentra: <b>Activo</b></p>'
                        elif status == "07":
                            self.state_fe = False
                            message_description += '<p>El servicio de factura electrónica se encuentra: <b>Inactivo</b></p>'
                        elif status == '02':
                            _logger.info('E-INV CR - No se encontraron los parametros esperados')
                            message_description += '<p>No se encontraron los parametros esperados</p>'
                        elif status == '03':
                            _logger.info('E-INV CR - No se encontro cliente con la identificacion enviada')
                            message_description += '<p>No se encontro cliente con la identificacion enviada</p>'
                        elif status == '04':
                            _logger.info('E-INV CR - Valor del parametro tipo inesperado')
                            message_description += '<p>Valor del parametro tipo inesperado</p>'
                        elif status == '05':
                            _logger.info('E-INV CR - Metodo inesperado')
                            message_description += '<p>Metodo inesperado</p>'
                        elif status == '06':
                            _logger.info('E-INV CR - No posee ninguna suscripción')
                            message_description += '<p>No posee ninguna suscripción activa</p>'
                        elif status == '09':
                            _logger.info('E-INV CR - Los datos indicados no son correctos')
                            message_description += '<p>Los datos indicados no son correctos</p>'
                        self.message_post(body=message_description)
            else:
                raise UserError(('El servidor no respondió correctamente'))
        except:
            raise UserError(('Ocurrió un error al validar el estado de su servicio'))

    def send_report(self):
        _logger.info('E-INV CR - Check partner key')
        companies = self.env['res.company'].search([])

        for company in companies:
            try:
                parametros = {'r': 'Reporte', 'id': str(company.vat),
                              'n_fe': str(company.n_fe),
                              'n_fee': str(company.n_fee),
                              'n_te': str(company.n_te),
                              'n_nc': str(company.n_nc),
                              'n_nd': str(company.n_nd),
                              'n_cce': str(company.n_cce),
                              'n_cpce': str(company.n_cpce),
                              'n_rce': str(company.n_rce),
                              'n_fec': str(company.n_fec)
                              }
                print(parametros)
                response = requests.get(str(company.url_tir), params=parametros)
                if 200 <= response.status_code <= 299:
                    response_json = response.json()
                    print(response_json)
                    codigo = response_json.get('Codigo')
                    if codigo == '09':
                        _logger.info('E-INV CR - Se recibió correctamente el reporte')
                        _logger.info('E-INV CR - Se reiniciarán los contadores')
                        company.n_fe = 0
                        company.n_fee = 0
                        company.n_te = 0
                        company.n_nc = 0
                        company.n_nd = 0
                        company.n_cce = 0
                        company.n_cpce = 0
                        company.n_rce = 0
                        company.n_fec = 0
                        _logger.info('E-INV CR - Se reiniciaron correctamente')

                else:
                    raise UserError(('El servidor no respondió correctamente'))
            except:
                raise UserError(('Ocurrió un error al validar el estado de su servicio'))

    def action_get_economic_activities(self):
        if self.vat:
            json_response = api_facturae.get_economic_activities(self)

            self.env.cr.execute('update economic_activity set active=False')

            self.message_post(subject='Actividades Económicas',
                              body='Aviso!.\n Cargando actividades económicas desde Hacienda')

            if json_response["status"] == 200:
                activities = json_response["activities"]
                activities_codes = list()
                for activity in activities:
                    if activity["estado"] == "A":
                        activities_codes.append(activity["codigo"])

                economic_activities = self.env['economic.activity'].with_context(active_test=False).search(
                    [('code', 'in', activities_codes)])

                for activity in economic_activities:
                    activity.active = True

                self.name = json_response["name"]
            else:
                alert = {
                    'title': json_response["status"],
                    'message': json_response["text"]
                }
                return {'value': {'vat': ''}, 'warning': alert}
        else:
            alert = {
                'title': 'Atención',
                'message': _('Company VAT is invalid')
            }
            return {'value': {'vat': ''}, 'warning': alert}
