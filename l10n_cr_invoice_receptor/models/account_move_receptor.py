# -*- coding: utf-8 -*-

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

from odoo.exceptions import ValidationError, UserError

try:
    from lxml import etree
except ImportError:
    from xml.etree import ElementTree

from . import api_facturae
from .. import extensions

class InvoiceReceptor(models.Model):

    _name = 'account.move.receptor'
    _description = 'Incoming Invoice Mail'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Boolean(string='Estado',)

    company_id = fields.Many2one(
        'res.company', "Company", default=lambda self: self.env.company, required=True)

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
         ('4', 'Preparado para importar'),
         ('5', 'Comprobante Rechazado')],
        string="Estado Documento Interno",
        required=False, default='2', readonly=True)
    documento_ref = fields.Many2one('account.move', string='Documento de Referencia', required=False, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Socio de Negocio', required=False, readonly=True)

    purchase_order = fields.Many2one('purchase.order', string='Orden de Compra')

    '''
        Campos para controlar el tema de rechazar sin tener que crear el documento en Odoo.
        Esto controla que ese registro no se pueda eliminar debido a que por ley se debe almacenar el comprobante por 5 años
    '''

    removable = fields.Boolean(string='Removable', default=True)

    state_tributacion = fields.Selection([('aceptado', 'Aceptado'),
                                          ('rechazado', 'Rechazado'),
                                          ('recibido', 'Recibido'),
                                          ('firma_invalida', 'Firma Inválida'),
                                          ('error', 'Error'),
                                          ('procesando', 'Procesando'),
                                          ('na', 'No Aplica'),
                                          ('ne', 'No Encontrado')],
                                         'Estado FE',
                                         copy=False)

    state_invoice_partner = fields.Selection(
        [('1', 'Aceptado'),
         ('2', 'Aceptacion parcial'),
         ('3', 'Rechazado')],
        'Respuesta del Cliente')

    tipo_documento_answr = fields.Selection(
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

    xml_comprobante = fields.Binary(
        string="Comprobante XML", required=False, copy=False, attachment=True)
    fname_xml_comprobante = fields.Char(
        string="Nombre de archivo Comprobante XML", required=False, copy=False,
        attachment=True)

    xml_respuesta_tributacion = fields.Binary(string="Respuesta Tributación XML", required=False, copy=False,
                                              attachment=True)

    fname_xml_respuesta_tributacion = fields.Char(
        string="Nombre de archivo XML Respuesta Tributación", required=False,
        copy=False)

    consecutive_number_receiver = fields.Char(string="Número Consecutivo Receptor", required=False, copy=False,
                                              readonly=True, index=True)


    def reject_invoice(self):
        for inv in self:
            inv.state_invoice_partner = '3'
            inv.removable = False
            if inv.xml:
                '''Verificar si el MR ya fue enviado y estamos esperando la confirmación'''
                if inv.state_tributacion == 'procesando':

                    token_m_h = api_facturae.get_token_hacienda(
                        inv, inv.company_id.frm_ws_ambiente)

                    api_facturae.consulta_documentos(inv, inv,
                                                     inv.company_id.frm_ws_ambiente,
                                                     token_m_h,
                                                     api_facturae.get_time_hacienda(),
                                                     False)
                else:
                    if inv.state_tributacion and inv.state_tributacion in ('aceptado', 'rechazado', 'na'):
                        raise UserError('Aviso!.\n La factura de proveedor ya fue confirmada')
                    
                    if not inv.xml:
                        inv.state_tributacion = 'error'
                        inv.message_post(
                            subject='Error',
                            body='Aviso!.\n No se ha cargado archivo XML')
                        continue
                    elif not inv.company_id.sucursal_MR or not inv.company_id.terminal_MR:
                        inv.state_tributacion = 'error'
                        inv.message_post(subject='Error',
                                         body='Aviso!.\nPor favor configure el diario de compras, terminal y sucursal')
                        continue

                    if not inv.state_invoice_partner:
                        inv.state_tributacion = 'error'
                        inv.message_post(subject='Error',
                                         body='Aviso!.\nDebe primero seleccionar el tipo de respuesta para el archivo cargado.')
                        continue

                    if inv.company_id.frm_ws_ambiente != 'disabled' and inv.state_invoice_partner:

                        # url = self.company_id.frm_callback_url
                        message_description = "<p><b>Enviando Mensaje Receptor</b></p>"

                        '''Si por el contrario es un documento nuevo, asignamos todos los valores'''
                        if not inv.xml_comprobante or inv.state_invoice_partner not in ['procesando', 'aceptado']:

                            if inv.state_invoice_partner == '1':
                                detalle_mensaje = 'Aceptado'
                                tipo = 1
                                tipo_documento = 'CCE'
                                sequence = inv.company_id.CCE_sequence_id.next_by_id()
                                # Contador de Aceptacion
                                inv.company_id.n_cce += 1

                            elif inv.state_invoice_partner == '2':
                                detalle_mensaje = 'Aceptado parcial'
                                tipo = 2
                                tipo_documento = 'CPCE'
                                sequence = inv.company_id.CPCE_sequence_id.next_by_id()
                                # Contador de Aceptacion Parcial
                                inv.company_id.n_cpce += 1
                            else:
                                detalle_mensaje = 'Rechazado'
                                tipo = 3
                                tipo_documento = 'RCE'
                                sequence = inv.company_id.RCE_sequence_id.next_by_id()
                                # Contador de Rechazo
                                inv.company_id.n_rce += 1

                            '''Si el mensaje fue rechazado, necesitamos generar un nuevo id'''
                            if inv.state_tributacion == 'rechazado' or inv.state_tributacion == 'error':
                                message_description += '<p><b>Cambiando consecutivo del Mensaje de Receptor</b> <br />' \
                                                       '<b>Consecutivo anterior: </b>' + inv.consecutive_number_receiver + \
                                                       '<br/>' \
                                                       '<b>Estado anterior: </b>' + inv.state_tributacion + '</p>'

                            '''Solicitamos la clave para el Mensaje Receptor'''
                            response_json = api_facturae.get_clave_hacienda(
                                inv, tipo_documento, sequence,
                                inv.company_id.sucursal_MR,
                                inv.company_id.terminal_MR)

                            inv.consecutive_number_receiver = response_json.get(
                                'consecutivo')
                            '''Generamos el Mensaje Receptor'''
                            if inv.t_venta is None or inv.t_venta == 0:
                                inv.state_tributacion = 'error'
                                inv.message_post(subject='Error',
                                                 body='El monto Total de la Factura para el Mensaje Receptro es inválido')
                                continue

                            xml = api_facturae.gen_xml_mr_43(
                                inv.n_clave, inv.partner_id.vat,
                                inv.date_issuance,
                                tipo, detalle_mensaje, inv.company_id.vat,
                                inv.consecutive_number_receiver,
                                inv.imp_mr,
                                inv.t_venta,
                                inv.company_id.activity_id.code,
                                '01')

                            xml_firmado = api_facturae.sign_xml(
                                inv.company_id.signature,
                                inv.company_id.frm_pin, xml)

                            inv.fname_xml_comprobante = tipo_documento + '_' + inv.n_documento + '.xml'

                            inv.xml_comprobante = base64.encodestring(xml_firmado)
                            inv.tipo_documento_answr = tipo_documento

                            if inv.state_tributacion != 'procesando':

                                env = inv.company_id.frm_ws_ambiente
                                token_m_h = api_facturae.get_token_hacienda(
                                    inv, inv.company_id.frm_ws_ambiente)

                                response_json = api_facturae.send_message(
                                    inv, api_facturae.get_time_hacienda(),
                                    xml_firmado,
                                    token_m_h, env)
                                status = response_json.get('status')

                                if 200 <= status <= 299:
                                    inv.state_tributacion = 'procesando'
                                else:
                                    inv.state_tributacion = 'error'
                                    _logger.error(
                                        'E-INV CR - Invoice: %s  Error sending Acceptance Message: %s',
                                        inv.n_documento,
                                        response_json.get('text'))

                                if inv.state_tributacion == 'procesando':
                                    token_m_h = api_facturae.get_token_hacienda(
                                        inv, inv.company_id.frm_ws_ambiente)

                                    if not token_m_h:
                                        _logger.error(
                                            'E-INV CR - Send Acceptance Message - HALTED - Failed to get token')
                                        return

                                    _logger.error(
                                        'E-INV CR - send_mrs_to_hacienda - 013')

                                    response_json = api_facturae.consulta_clave(
                                        inv.n_documento + '-' + inv.consecutive_number_receiver,
                                        token_m_h,
                                        inv.company_id.frm_ws_ambiente)
                                    status = response_json['status']

                                    if status == 200:
                                        inv.state_tributacion = response_json.get(
                                            'ind-estado')
                                        inv.xml_respuesta_tributacion = response_json.get(
                                            'respuesta-xml')
                                        inv.fname_xml_respuesta_tributacion = 'ACH_' + \
                                                                              inv.n_documento + '-' + inv.consecutive_number_receiver + '.xml'

                                        _logger.error(
                                            'E-INV CR - Estado Documento:%s',
                                            inv.state_tributacion)

                                        message_description += '<p><b>Ha enviado Mensaje de Receptor</b>' + \
                                                               '<br /><b>Documento: </b>' + inv.n_documento + \
                                                               '<br /><b>Consecutivo de mensaje: </b>' + \
                                                               inv.consecutive_number_receiver + \
                                                               '<br/><b>Mensaje indicado:</b>' \
                                                               + detalle_mensaje + '</p>'

                                        self.message_post(
                                            body=message_description,
                                            # subtype='mail.mt_note',
                                            content_subtype='html')

                                        _logger.info(
                                            'E-INV CR - Estado Documento:%s',
                                            inv.state_tributacion)

                                    elif status == 400:
                                        inv.state_tributacion = 'ne'
                                        _logger.error(
                                            'MAB - Aceptacion Documento:%s no encontrado en Hacienda.',
                                            inv.n_documento + '-' + inv.consecutive_number_receiver)
                                    else:
                                        _logger.error(
                                            'MAB - Error inesperado en Send Acceptance File - Abortando')
                                        return


    def unlink(self):
        for doc in self:
            if doc.removable == False:
                if doc.name:
                    name = doc.name
                else:
                    name = 'No definido, (ID: ' + str(doc.id) + ')'
                _logger.info('E-INV-RECEPT TIR - No se puede eliminar el registro: ' + name)
                raise UserError(_('No se puede eliminar el registro: ' + name))
            else:
                super(InvoiceReceptor, doc).unlink()


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
                        [('vat', '=', document.nif_emisor), ('type', '=', 'contact'), ('parent_id', '=', False)], limit=1)
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
        if self.purchase_order and self.partner_id and self.state_doc_ref in ['2','4']:
            self.purchase_order.move_receptor = self.id

            invoice = self.env['account.move'].sudo().search([('move_type', 'in', ['in_invoice', 'in_refund']), ('invoice_origin', '=', self.purchase_order.name), ('state', 'in', ('posted', 'draft'))], limit=1)
            if len(invoice) > 0:
                invoice.xml_supplier_approval = self.xml
                invoice.fname_xml_supplier_approval = self.name_xml

                if self.tipo_documento == 'FE':
                    invoice.tipo_documento = 'FE'
                if self.tipo_documento == 'NC':
                    invoice.tipo_documento = 'NC'
                if self.tipo_documento == 'ND':
                    invoice.tipo_documento = 'ND'

                if self.pdf_id:
                    message_description = '<p>Este documento está a la espera de su aprobación</p>'
                    invoice.message_post(body=message_description,
                                         attachments=[(self.pdf_id.name, base64.b64decode(self.pdf_id.datas))])
                else:
                    message_description = '<p>Este documento está a la espera de su aprobación</p>'

                    invoice.message_post(
                        body=message_description,
                        # subtype='mail.mt_note',
                        content_subtype='html')

                self.state = True
                self.documento_ref = invoice.id
                self.state_doc_ref = '1'
                invoice.load_xml_data()
            else:
                message_description = '<p>La orden de compra aun no está facturada, por favor realice la factura correspondiente</p>'

                self.message_post(
                    body=message_description,
                    # subtype='mail.mt_note',
                    content_subtype='html')
        else:
            if self.state_doc_ref in ['2','4'] and self.partner_id:

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
                        partner = self.env['res.partner'].search([('vat', '=', self.nif_emisor), ('type', '=', 'contact')], limit=1)
                        if len(partner) > 0:
                            Info['partner_id'] = partner.id
                            Info['date'] = self.date_issuance
                            Info['invoice_date'] = self.date_issuance

                            Info['state'] = 'draft'
                            if self.tipo_documento == 'FE':
                                Info['move_type'] = 'in_invoice'
                                Info['tipo_documento'] = 'FE'
                            if self.tipo_documento == 'NC':
                                Info['move_type'] = 'in_refund'
                                Info['tipo_documento'] = 'NC'
                            if self.tipo_documento == 'ND':
                                Info['move_type'] = 'in_invoice'
                                Info['tipo_documento'] = 'ND'
                            Info['currency_id'] = self.currency_id.id

                            diario = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)

                            if diario:
                                Info['journal_id'] = diario.id
                            _logger.info("VALOR DE INFO")
                            _logger.info(Info)
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
                            invoice.currency_id = self.currency_id.id
                            invoice.load_xml_data()
                            if self.tipo_documento == 'FE':
                                invoice.tipo_documento = 'FE'
                            if self.tipo_documento == 'NC':
                                invoice.tipo_documento = 'NC'
                            if self.tipo_documento == 'ND':
                                invoice.tipo_documento = 'ND'
                            #invoice.tipo_documento = 'CCE'
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
        info = {}
        if self.r_social_emisor:
            info['name'] = self.r_social_emisor

        invoice_xml = etree.fromstring(base64.b64decode(self.xml))
        namespaces = invoice_xml.nsmap
        inv_xmlns = namespaces.pop(None)
        namespaces['inv'] = inv_xmlns

        info['vat'] = invoice_xml.xpath("inv:Emisor/inv:Identificacion/inv:Numero", namespaces=namespaces)[0].text

        partner = self.env['res.partner'].search([('vat', '=', info['vat']), ('type', '=', 'contact'),('parent_id', '=', False)], limit=1)
        if len(partner) > 0:
            self.partner_id = partner.id
            self.state_doc_ref = '4'
        else:
            try:
                info['phone'] = invoice_xml.xpath("inv:Emisor/inv:Telefono/inv:NumTelefono", namespaces=namespaces)[0].text
            except IndexError:
                info['phone'] = False
            try:
                info['email'] = invoice_xml.xpath("inv:Emisor/inv:CorreoElectronico", namespaces=namespaces)[0].text
            except IndexError:
                info['email'] = False
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

            cliente = self.env['res.partner'].create(info)
            cliente.onchange_vat()

            self.partner_id = cliente.id
            self.state_doc_ref = '4'
