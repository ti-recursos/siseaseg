# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
import poplib
from ssl import SSLError
from socket import gaierror, timeout
from imaplib import IMAP4, IMAP4_SSL
from poplib import POP3, POP3_SSL

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

import datetime

_logger = logging.getLogger(__name__)

try:
    from lxml import etree
except ImportError:
    from xml.etree import ElementTree

class InvoiceReceptor(models.Model):

    _name = 'account.move.receptor'
    _description = 'Incoming Invoice Mail'

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Boolean(string='Estado',)

    '''
        Adjuntos del correo
    '''
    pdf_id = fields.Many2one("ir.attachment", string="Documento PDF", required=False, )

    name_xml = fields.Char(string='XML FE', readonly=True)
    xml = fields.Binary(string="XML Factura Electrónica", required=False, copy=False, attachment=True)
    name_mr = fields.Char(string='XML MR', readonly=True)
    xml_mr = fields.Binary(string="XML Respuesta de MH", required=False, copy=False, attachment=True)

    temp_name = fields.Char(string='Nombre XML Temporal', readonly=True)
    xml_temp = fields.Binary(string="XML Temporal", required=False, copy=False, attachment=True)

    '''
        Documento Electrónico Recibido
        Tipos: FE, NCE, NDE
    '''
    tipo_documento = fields.Selection(
        selection=[('FE', 'Factura Electrónica'),
                   ('FEE', 'Factura Electrónica de Exportación'),
                   ('TE', 'Tiquete Electrónico'),
                   ('NC', 'Nota de Crédito'),
                   ('ND', 'Nota de Débito'),
                   ('CCE', 'MR Aceptación'),
                   ('CPCE', 'MR Aceptación Parcial'),
                   ('RCE', 'MR Rechazo'),
                   ('FEC', 'Factura Electrónica de Compra'),
                   ('disabled', 'Electronic Documents Disabled')],
        string="Tipo Comprobante",
        required=False, default='FE',
        help='Indica el tipo de documento de acuerdo a la '
             'clasificación del Ministerio de Hacienda')

    n_documento = fields.Char(string='Número de Documento', readonly=True)
    n_clave = fields.Char(string='Número de Clave', readonly=True)
    date_issuance = fields.Datetime(string='Fecha Emisión', readonly=True)
    nif_emisor = fields.Char(string='Identificación Emisor', readonly=True)
    r_social_emisor = fields.Char(string='Razón Social Emisor', readonly=True)
    n_comercial_emisor = fields.Char(string='Nombre Comercial Emisor', readonly=True)
    nif_receptor = fields.Char(string='Identificación Receptor', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, readonly=True)
    t_venta = fields.Monetary(string='Total Venta', readonly=True)
    date_doc = fields.Datetime(string='Fecha Creación', readonly=True)

    '''
        Mensaje Hacienda
    '''
    state_mr = fields.Selection(
        [('1', 'Aceptado'),
         ('2', 'Aceptacion parcial'),
         ('3', 'Rechazado')],
         'Estado MR', readonly=True)
    date_mr = fields.Datetime(string='Fecha Aceptación MR', readonly=True)
    n_clave_mr = fields.Char(string='Número de Clave MR', readonly=True)
    imp_mr = fields.Monetary(string='Impuesto MR', readonly=True)
    total_mr = fields.Monetary(string='Total MR', readonly=True)
    mensaje_hacienda = fields.Text(string='Mensaje de Hacienda', readonly=True)

    state_doc_ref = fields.Selection(
        [('1', 'Creado'),
         ('2', 'En Proceso'),
         ('3', 'El emisor no existe en el sistema'),
         ('4', 'Preparado para importar')],
        string="Estado Documento Interno",
        required=False, default='2', readonly=True)
    documento_ref = fields.Many2one('account.move', string='Documento de Referencia', required=False, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Socio de Negocio', required=False, readonly=True)

    @api.model
    def _create_documents(self):

        _logger.info('E-INV-RECEPT TIR - Ejecutando _create_documents')
        documentos = self.env['account.move.receptor'].search(
            [('state', '=', False), ('state_mr', 'in', ['1', '2']), ('state_doc_ref', '=', '2')], limit=10)
        for doc in documentos:
            partner = self.env['res.partner'].search(
                [('vat', '=', doc.nif_emisor), ('type', '=', 'contact'),
                 ('property_supplier_payment_term_id', '!=', False), ('parent_id', '=', False)], limit=1)
            if len(partner) > 0:
                doc.partner_id = partner.id

            if doc.state_doc_ref == '2' and doc.partner_id:
                _logger.info('E-INV-RECEPT TIR - El cliente existe en la base de datos')
                doc.state_doc_ref = '4'
            else:
                _logger.info('E-INV-RECEPT TIR - El cliente no existe en la base de datos')
                doc.state_doc_ref = '3'
        '''
            Busco los últimos 10 documentos para crear su respectivo documento borrador
        '''
        _logger.info('E-INV-RECEPT TIR - Ejecutando _create_documents')
        documents = self.env['account.move.receptor'].search([('state', '=', False), ('state_mr', 'in', ['1','2']), ('state_doc_ref', '=', '4')], limit=10)

        _logger.info('E-INV-RECEPT TIR - Recorriendo ' + str(len(documents)) + ' documentos')
        for document in documents:

            if document.state_doc_ref == '4' and document.partner_id:
                Info = {}
                _logger.info('E-INV-RECEPT TIR - Buscando si existe el documento ya creado en el sistema')
                documento_electronico = self.env['account.move'].search([('number_electronic', '=', document.n_clave), ('move_type','in',['in_invoice', 'in_refund'])], limit=1)

                if len(documento_electronico) == 1:
                    _logger.info('E-INV-RECEPT TIR - El documento existe en el sistema')
                    document.state = True
                    document.documento_ref = documento_electronico.id
                    document.state_doc_ref = '1'
                else:
                    _logger.info('E-INV-RECEPT TIR - El documento no existe en el sistema, se creará uno nuevo')
                    partner = self.env['res.partner'].search(
                        [('vat', '=', document.nif_emisor), ('type', '=', 'contact'),
                         ('property_supplier_payment_term_id', '!=', False), ('parent_id', '=', False)], limit=1)
                    if len(partner) > 0:
                        Info['partner_id'] = partner.id
                        Info['date'] = document.date_issuance
                        Info['invoice_date'] = document.date_issuance

                        Info['state'] = 'draft'
                        if document.tipo_documento == 'FE':
                            Info['move_type'] = 'in_invoice'
                        if document.tipo_documento == 'NC':
                            Info['move_type'] = 'in_refund'
                        if document.tipo_documento == 'ND':
                            Info['move_type'] = 'in_invoice'

                        Info['currency_id'] = document.currency_id.id

                        diario = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)

                        if diario:
                            Info['journal_id'] = diario.id

                        invoice = self.env['account.move'].create(Info)

                        if invoice.partner_id:
                            invoice.payment_methods_id = invoice.partner_id.payment_methods_id.id
                        invoice.xml_supplier_approval = document.xml
                        invoice.fname_xml_supplier_approval = document.name_xml
                        invoice.load_xml_data()

                        message_description = '<p>Este documento fue generado automáticamente y está a la espera de su aprobación</p>'

                        invoice.message_post(
                            body=message_description,
                            # subtype='mail.mt_note',
                            content_subtype='html')
                        if document.pdf_id:
                            message_description = '<p>Este documento fue generado automáticamente y está a la espera de su aprobación</p>'
                            invoice.message_post(body=message_description,
                                                 attachments=[(document.pdf_id.name, base64.b64decode(document.pdf_id.datas))])
                        else:
                            message_description = '<p>Este documento fue generado automáticamente y está a la espera de su aprobación</p>'

                            invoice.message_post(
                                body=message_description,
                                # subtype='mail.mt_note',
                                content_subtype='html')

                        document.state = True
                        document.documento_ref = invoice.id
                        document.state_doc_ref = '1'
                        invoice.tipo_documento = 'CCE'
                    else:
                        _logger.info('E-INV-RECEPT TIR - El cliente no existe en la base de datos')
                        document.state_doc_ref = '3'
            else:
                partner = self.env['res.partner'].search([('vat', '=', document.nif_emisor), ('type', '=', 'contact'),
                                                          ('property_supplier_payment_term_id', '!=', False),
                                                          ('parent_id', '=', False)], limit=1)
                if partner:
                    document.partner_id = partner.id
                else:
                    _logger.info('E-INV-RECEPT TIR - El cliente no existe en la base de datos')
                    document.state_doc_ref = '3'

    def create_document_manual(self):

        _logger.info('E-INV-RECEPT TIR - Ejecutando _create_document_manual')
        if self.state_doc_ref == '2' and self.partner_id:

            Info = {}
            _logger.info('E-INV-RECEPT TIR - Buscando si existe el documento ya creado en el sistema')
            documento_electronico = self.env['account.move'].search(
                [('number_electronic', '=', self.n_clave), ('move_type', 'in', ['in_invoice', 'in_refund'])],
                limit=1)

            if len(documento_electronico) == 1:
                _logger.info('E-INV-RECEPT TIR - El documento existe en el sistema')
                self.state = True
                self.documento_ref = documento_electronico.id
                self.state_doc_ref = '1'
            else:
                _logger.info('E-INV-RECEPT TIR - El documento no existe en el sistema, se creará uno nuevo')
                try:
                    partner = self.env['res.partner'].search([('vat', '=', self.nif_emisor), ('type', '=', 'contact'), ('property_supplier_payment_term_id', '!=', False), ('parent_id', '=', False)], limit=1)
                    if len(partner) > 0:
                        Info['partner_id'] = partner.id
                        Info['date'] = self.date_issuance
                        Info['invoice_date'] = self.date_issuance

                        Info['state'] = 'draft'
                        if self.tipo_documento == 'FE':
                            Info['move_type'] = 'in_invoice'
                        if self.tipo_documento == 'NC':
                            Info['move_type'] = 'in_refund'
                        if self.tipo_documento == 'ND':
                            Info['move_type'] = 'in_invoice'

                        Info['currency_id'] = self.currency_id.id

                        diario = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)

                        if diario:
                            Info['journal_id'] = diario.id

                        invoice = self.env['account.move'].create(Info)

                        if invoice.partner_id:
                            invoice.payment_methods_id = invoice.partner_id.payment_methods_id
                        invoice.xml_supplier_approval = self.xml
                        invoice.fname_xml_supplier_approval = self.name_xml

                        if self.pdf_id:
                            message_description = '<p>Este documento fue generado automáticamente y está a la espera de su aprobación</p>'
                            invoice.message_post(body=message_description, attachments=[(self.pdf_id.name, base64.b64decode(self.pdf_id.datas))])
                        else:
                            message_description = '<p>Este documento fue generado automáticamente y está a la espera de su aprobación</p>'

                            invoice.message_post(
                                body=message_description,
                                # subtype='mail.mt_note',
                                content_subtype='html')

                        self.state = True
                        self.documento_ref = invoice.id
                        self.state_doc_ref = '1'

                        invoice.load_xml_data()
                        invoice.tipo_documento = 'CCE'
                    else:
                        _logger.info('E-INV-RECEPT TIR - El cliente no existe en la base de datos')
                        self.state_doc_ref = '3'
                except:
                    _logger.info('E-INV-RECEPT TIR - El cliente no existe en la base de datos')
                    self.state_doc_ref = '3'
        else:
            partner = self.env['res.partner'].search([('vat', '=', self.nif_emisor), ('type', '=', 'contact'),
                                                      ('property_supplier_payment_term_id', '!=', False),
                                                      ('parent_id', '=', False)], limit=1)
            if partner:
                self.partner_id = partner.id
            else:
                _logger.info('E-INV-RECEPT TIR - El cliente no existe en la base de datos')
                self.state_doc_ref = '3'

    @api.onchange('nif_emisor')
    def onchange_nif_emisor(self):
        if self.nif_emisor:
            partner = self.env['res.partner'].search([('vat', '=', self.nif_emisor), ('type', '=', 'contact'), ('property_supplier_payment_term_id', '!=', False), ('parent_id', '=', False)], limit=1)
            if partner:
                self.partner_id = partner.id

    def create_partner(self):
        print('Create Partner')

        info = {}
        if self.r_social_emisor:
            info['name'] = self.r_social_emisor

        invoice_xml = etree.fromstring(base64.b64decode(self.xml))
        namespaces = invoice_xml.nsmap
        inv_xmlns = namespaces.pop(None)
        namespaces['inv'] = inv_xmlns

        info['vat'] = invoice_xml.xpath("inv:Emisor/inv:Identificacion/inv:Numero", namespaces=namespaces)[0].text
        info['phone'] = invoice_xml.xpath("inv:Emisor/inv:Telefono/inv:NumTelefono", namespaces=namespaces)[0].text
        info['email'] = invoice_xml.xpath("inv:Emisor/inv:CorreoElectronico", namespaces=namespaces)[0].text
        info['lang'] = 'es_CR'

        # Se agrega manualmente la información ya que no se puede obtener del XML
        info['property_payment_term_id'] = 1
        info['payment_methods_id'] = 1
        info['property_product_pricelist'] = 1
        info['property_supplier_payment_term_id'] = 1

        # Ubicacion

        # País
        info['country_id'] = self.env['res.country'].search([('code', '=', 'CR')], limit=1).id

        # Provincia
        provincia = invoice_xml.xpath("inv:Emisor/inv:Ubicacion/inv:Provincia", namespaces=namespaces)[0].text
        state_id = self.env['res.country.state'].search([('code', '=', provincia)], limit=1).id
        info['state_id'] = state_id

        # Cantón
        canton = invoice_xml.xpath("inv:Emisor/inv:Ubicacion/inv:Canton", namespaces=namespaces)[0].text
        county_id = self.env['res.country.county'].search([('code', '=', canton), ('state_id', '=', state_id)], limit=1).id
        info['county_id'] = county_id

        # Distrito
        distrito = invoice_xml.xpath("inv:Emisor/inv:Ubicacion/inv:Distrito", namespaces=namespaces)[0].text
        district_id = self.env['res.country.district'].search([('code', '=', distrito), ('county_id', '=', county_id)], limit=1).id
        info['district_id'] = district_id


        actividad_economica = invoice_xml.xpath("inv:CodigoActividad", namespaces=namespaces)[0].text
        info['activity_id'] = self.env['economic.activity'].search([('active', '=', True), ('code', '=', actividad_economica)], limit=1).id

        print(info)

        cliente = self.env['res.partner'].create(info)
        cliente.onchange_vat()

        self.partner_id = cliente.id
        self.state_doc_ref = '4'