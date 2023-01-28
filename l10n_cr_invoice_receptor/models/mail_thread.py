# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import base64
import datetime
import dateutil
import email
import email.policy
import hashlib
import hmac
import lxml
import logging
import pytz
import re
import socket
import time
import threading
import base64
import io
import zipfile
from os.path import join

from collections import namedtuple
from email.message import EmailMessage
from email import message_from_string, policy
from lxml import etree
from werkzeug import urls
from xmlrpc import client as xmlrpclib

from odoo import _, api, exceptions, fields, models, tools, registry, SUPERUSER_ID
from odoo.exceptions import MissingError
from odoo.osv import expression

from odoo.exceptions import UserError


from odoo.tools import ustr
from odoo.tools.misc import clean_context, split_every

_logger = logging.getLogger(__name__)

try:
    from lxml import etree
except ImportError:
    from xml.etree import ElementTree

# from odoo.addons.cr_electronic_invoice.models import api_facturae


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def str_time_to_utc(self, fecha):
        local = pytz.timezone("America/Costa_Rica")
        naive = datetime.datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")
        local_dt = local.localize(naive, is_dst=None)
        dato = local_dt.astimezone(pytz.utc)
        return dato.strftime("%Y-%m-%d %H:%M:00")

    def convert_TZ_UTC(self, TZ_datetime):
        fmt = '%Y-%m-%dT%H:%M'
        # Current time in UTC
        now_utc = datetime.datetime.now(pytz.timezone('UTC'))
        # Convert to current user time zone
        now_timezone = now_utc.astimezone(pytz.timezone(self.env.user.tz))
        UTC_OFFSET_TIMEDELTA = datetime.datetime.strptime(now_utc.strftime(fmt), fmt) - datetime.datetime.strptime(
            now_timezone.strftime(fmt), fmt)
        local_datetime = datetime.datetime.strptime(TZ_datetime, fmt)
        result_utc_datetime = local_datetime + UTC_OFFSET_TIMEDELTA

        return result_utc_datetime

    def process_mr(self, invoice_xml, invoice):
        _logger.info('E-INV-RECEPT TIR - Ejecutando process_mr')
        namespaces = invoice_xml.nsmap
        inv_xmlns = namespaces.pop(None)
        namespaces['inv'] = inv_xmlns
        #invoice.state_doc_ref = '2'
        if 0 < len(invoice_xml.xpath("inv:NumeroCedulaReceptor", namespaces=namespaces)):
            nif_receptor = invoice_xml.xpath("inv:NumeroCedulaReceptor", namespaces=namespaces)[0].text
            company = self.env.user.company_id

            if nif_receptor != company.vat:
                _logger.info('E-INV-RECEPT TIR - La identificación del XML es diferente a la de la compañia')
                invoice.unlink()
            else:
                if 0 < len(invoice_xml.xpath("inv:Clave", namespaces=namespaces)):
                    n_clave = invoice_xml.xpath("inv:Clave", namespaces=namespaces)[0].text
                    invoice.n_clave = n_clave
                    invoice.name = n_clave

                    existente = self.env['account.move.receptor'].search([('n_clave', '=', n_clave), ('id', '!=', invoice.id)], limit=1)

                    if len(existente) == 1:
                        _logger.info('E-INV-RECEPT TIR - El MR ya existía en nuestra base de datos')
                        if invoice.id != existente.id:
                            existente.name_mr = invoice.temp_name
                            existente.xml_mr = invoice.xml_temp
                            if invoice.pdf_id:
                                existente.pdf_id = invoice.pdf_id
                            invoice.unlink()

                            existente.state_mr = invoice_xml.xpath("inv:Mensaje", namespaces=namespaces)[0].text
                            existente.mensaje_hacienda = invoice_xml.xpath("inv:DetalleMensaje", namespaces=namespaces)[0].text

                            now_utc = datetime.datetime.now(pytz.timezone('UTC'))
                            now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
                            dia = now_cr.strftime('%d')  # '%02d' % now_cr.day,
                            mes = now_cr.strftime('%m')  # '%02d' % now_cr.month,
                            anno = now_cr.strftime('%Y')  # str(now_cr.year)[2:4],
                            date_cr = now_cr.strftime(anno + "-" + mes + "-" + dia + " %H:%M:%S")

                            existente.date_mr = self.str_time_to_utc(date_cr)

                            existente.n_clave_mr = n_clave
                            existente.name = n_clave

                            existente.imp_mr = float(invoice_xml.xpath("inv:MontoTotalImpuesto", namespaces=namespaces)[0].text)
                            existente.total_mr = float(invoice_xml.xpath("inv:TotalFactura", namespaces=namespaces)[0].text)
                            _logger.info('E-INV-RECEPT TIR - Se completó la actualización del MR')
                    else:
                        _logger.info('E-INV-RECEPT TIR - El MR no se encuentra en nuestra base de datos')
                        invoice.name_mr = invoice.temp_name
                        invoice.xml_mr = invoice.xml_temp

                        invoice.temp_name = False
                        invoice.xml_temp = False

                        invoice.state_mr = invoice_xml.xpath("inv:Mensaje", namespaces=namespaces)[0].text
                        invoice.mensaje_hacienda = invoice_xml.xpath("inv:DetalleMensaje", namespaces=namespaces)[0].text

                        invoice.n_clave_mr = n_clave
                        now_utc = datetime.datetime.now(pytz.timezone('UTC'))
                        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
                        dia = now_cr.strftime('%d')  # '%02d' % now_cr.day,
                        mes = now_cr.strftime('%m')  # '%02d' % now_cr.month,
                        anno = now_cr.strftime('%Y')  # str(now_cr.year)[2:4],
                        date_cr = now_cr.strftime(anno + "-" + mes + "-" + dia + " %H:%M:%S")

                        invoice.date_mr = self.str_time_to_utc(date_cr)

                        invoice.imp_mr = float(invoice_xml.xpath("inv:MontoTotalImpuesto", namespaces=namespaces)[0].text)
                        invoice.total_mr = float(invoice_xml.xpath("inv:TotalFactura", namespaces=namespaces)[0].text)
                        _logger.info('E-INV-RECEPT TIR - Se creó completamente el MR')


    def process_electronic_document(self, invoice_xml, invoice, tipo_documento):

        namespaces = invoice_xml.nsmap
        inv_xmlns = namespaces.pop(None)
        namespaces['inv'] = inv_xmlns
        n_clave = invoice_xml.xpath("inv:Clave", namespaces=namespaces)[0].text
        #invoice.state_doc_ref = '2'

        nif_receptor = invoice_xml.xpath("inv:Receptor/inv:Identificacion/inv:Numero", namespaces=namespaces)[0].text


        company = self.env.user.company_id

        if nif_receptor != company.vat:
            invoice.unlink()
        else:

            existente = self.env['account.move.receptor'].search([('n_clave', '=', n_clave), ('id', '!=', invoice.id)], limit=1)

            if len(existente) == 1:
                existente.tipo_documento = tipo_documento
                existente.name_xml = invoice.temp_name
                existente.xml = invoice.xml_temp
                if invoice.pdf_id:
                    existente.pdf_id = invoice.pdf_id

                if invoice.id != existente.id:
                    invoice.unlink()

                existente.temp_name = False
                existente.xml_temp = False

                existente.n_documento = invoice_xml.xpath("inv:NumeroConsecutivo", namespaces=namespaces)[0].text
                existente.n_clave = n_clave
                existente.name = n_clave

                emision = invoice_xml.xpath("inv:FechaEmision", namespaces=namespaces)[0].text
                existente.date_issuance = self.convert_TZ_UTC(str(emision[0:16]))

                existente.date_doc = existente.create_date

                existente.nif_emisor = invoice_xml.xpath("inv:Emisor/inv:Identificacion/inv:Numero", namespaces=namespaces)[0].text
                existente.r_social_emisor = invoice_xml.xpath("inv:Emisor/inv:Nombre", namespaces=namespaces)[0].text
                partner = self.env['res.partner'].search(
                    [('vat', '=', existente.nif_emisor), ('type', '=', 'contact')], limit=1)
                if len(partner) > 0:
                    existente.partner_id = partner.id

                if 0 < len(invoice_xml.xpath("inv:Emisor/inv:NombreComercial", namespaces=namespaces)):
                    existente.n_comercial_emisor = invoice_xml.xpath("inv:Emisor/inv:NombreComercial", namespaces=namespaces)[0].text

                existente.nif_receptor = invoice_xml.xpath("inv:Receptor/inv:Identificacion/inv:Numero", namespaces=namespaces)[0].text


                currency_node = invoice_xml.xpath("inv:ResumenFactura/inv:CodigoTipoMoneda/inv:CodigoMoneda",
                                                  namespaces=namespaces)
                if currency_node:
                    existente.currency_id = invoice.env['res.currency'].search([('name', '=', currency_node[0].text)],
                                                                             limit=1).id
                else:
                    existente.currency_id = invoice.env['res.currency'].search([('name', '=', 'CRC')], limit=1).id

                existente.t_venta = float(invoice_xml.xpath("inv:ResumenFactura/inv:TotalComprobante", namespaces=namespaces)[0].text)

            else:
                invoice.tipo_documento = tipo_documento
                invoice.name_xml = invoice.temp_name
                invoice.xml = invoice.xml_temp

                invoice.temp_name = False
                invoice.xml_temp = False

                invoice.n_documento = invoice_xml.xpath("inv:NumeroConsecutivo", namespaces=namespaces)[0].text

                invoice.n_clave_mr = n_clave
                invoice.n_clave = n_clave
                invoice.name = n_clave

                emision = invoice_xml.xpath("inv:FechaEmision", namespaces=namespaces)[0].text
                invoice.date_issuance = self.convert_TZ_UTC(str(emision[0:16]))

                invoice.date_doc = invoice.create_date

                invoice.nif_emisor = invoice_xml.xpath("inv:Emisor/inv:Identificacion/inv:Numero", namespaces=namespaces)[0].text

                invoice.r_social_emisor = invoice_xml.xpath("inv:Emisor/inv:Nombre", namespaces=namespaces)[0].text
                
                partner = self.env['res.partner'].search(
                    [('vat', '=', invoice.nif_emisor), ('type', '=', 'contact')], limit=1)
                if len(partner) > 0:
                    invoice.partner_id = partner.id

                if 0 < len(invoice_xml.xpath("inv:Emisor/inv:NombreComercial", namespaces=namespaces)):
                    invoice.n_comercial_emisor = invoice_xml.xpath("inv:Emisor/inv:NombreComercial", namespaces=namespaces)[0].text
                

                invoice.nif_receptor = invoice_xml.xpath("inv:Receptor/inv:Identificacion/inv:Numero", namespaces=namespaces)[0].text

                currency_node = invoice_xml.xpath("inv:ResumenFactura/inv:CodigoTipoMoneda/inv:CodigoMoneda", namespaces=namespaces)
                if currency_node:
                    invoice.currency_id = invoice.env['res.currency'].search([('name', '=', currency_node[0].text)], limit=1).id
                else:
                    invoice.currency_id = invoice.env['res.currency'].search([('name', '=', 'CRC')], limit=1).id

                invoice.t_venta = float(invoice_xml.xpath("inv:ResumenFactura/inv:TotalComprobante", namespaces=namespaces)[0].text)


    def process_xml_pdf(self, data, xml_name, pdf, pdf_name):
        _logger.info('E-INV-RECEPT TIR - Ejecutando process_xml')

        '''
        Ajuste para diferentes tipos de PDF
        '''
        if str(type(pdf)) in "<class 'str'>":
            _logger.info('E-INV-RECEPT TIR - El PDF es de tipo <class "str">')
            a = str(pdf).encode('ascii', errors='ignore').decode()
            message_bytes = a.encode('utf8')

            attachment_id = self.env['ir.attachment'].create({
                'name': pdf_name,
                'type': 'binary',
                'mimetype': 'application/pdf',
                'datas': base64.encodebytes(message_bytes),
                'res_model': self._name,
            })
            _logger.info('E-INV-RECEPT TIR - Se creó el PDF temporal')
        elif str(type(pdf)) in "<class 'bytes'>":
            _logger.info('E-INV-RECEPT TIR - El PDF es de tipo <class "str">')
            attachment_id = self.env['ir.attachment'].create({
                'name': pdf_name,
                'type': 'binary',
                'mimetype': 'application/pdf',
                'datas': base64.encodebytes(pdf),
                'res_model': self._name,
            })

            _logger.info('E-INV-RECEPT TIR - Se creó el PDF temporal')

        '''
        Ajuste para diferentes tipos de XML
        '''

        if str(type(data)) in "<class 'str'>":
            _logger.info('E-INV-RECEPT TIR - El documento es de tipo <class "str">')
            a = str(data).encode('ascii', errors='ignore').decode()
            message_bytes = a.encode('utf8')

            invoice = self.env['account.move.receptor'].create({
                'currency_id': 39,
                'temp_name': xml_name,
                'xml_temp': base64.encodebytes(message_bytes),
                'pdf_id': attachment_id.id

            })
            message_description = '<p>Este documento PDF fue enviado por el proveedor</p>'
            invoice.message_post(body=message_description,
                                 attachments=[(invoice.pdf_id.name, base64.b64decode(invoice.pdf_id.datas))])
            _logger.info('E-INV-RECEPT TIR - Se creó el fichero temporal')
        elif str(type(data)) in "<class 'bytes'>":
            _logger.info('E-INV-RECEPT TIR - El documento es de tipo <class "str">')
            invoice = self.env['account.move.receptor'].create({
                'currency_id': 39,
                'temp_name': xml_name,
                'xml_temp': base64.encodebytes(data),
                'pdf_id': attachment_id.id
            })
            message_description = '<p>Este documento PDF fue enviado por el proveedor</p>'
            invoice.message_post(body=message_description,
                                 attachments=[(invoice.pdf_id.name, base64.b64decode(invoice.pdf_id.datas))])

            _logger.info('E-INV-RECEPT TIR - Se creó el fichero temporal')
        try:
            _logger.info('E-INV-RECEPT TIR - Leyendo XML')
            invoice_xml = etree.fromstring(base64.b64decode(invoice.xml_temp))

            try:
                _logger.info('E-INV-RECEPT TIR - Buscando tipo de Documento')
                document_type = re.search('FacturaElectronica|NotaCreditoElectronica|NotaDebitoElectronica|TiqueteElectronico', invoice_xml.tag).group(0)

                if document_type == 'TiqueteElectronico':
                    raise UserError(_("This is a TICKET only invoices are valid for taxes"))
                if document_type in ('FacturaElectronica', 'NotaCreditoElectronica', 'NotaDebitoElectronica'):

                    if document_type == 'FacturaElectronica':
                        self.process_electronic_document(invoice_xml, invoice, 'FE')
                    if document_type == 'NotaCreditoElectronica':
                        self.process_electronic_document(invoice_xml, invoice, 'NC')
                    if document_type == 'NotaDebitoElectronica':
                        self.process_electronic_document(invoice_xml, invoice, 'ND')
            except:
                _logger.info('E-INV-RECEPT TIR - El XML puede ser un MR')
                self.process_mr(invoice_xml, invoice)


        except Exception as e:
            _logger.info('E-INV-RECEPT TIR - Ocurrió un error leyendo el archivo: ' + xml_name + " / " + pdf_name)

    def process_xml(self, data, xml_name):
        _logger.info('E-INV-RECEPT TIR - Ejecutando process_xml')
        if str(type(data)) in "<class 'str'>":
            _logger.info('E-INV-RECEPT TIR - El documento es de tipo <class "str">')
            a = str(data).encode('ascii', errors='ignore').decode()
            message_bytes = a.encode('utf8')
            invoice = self.env['account.move.receptor'].create({
                'currency_id': 39,
                'temp_name': xml_name,
                'xml_temp': base64.encodebytes(message_bytes)                

            })
            _logger.info('E-INV-RECEPT TIR - Se creó el fichero temporal')
        elif str(type(data)) in "<class 'bytes'>":
            _logger.info('E-INV-RECEPT TIR - El documento es de tipo <class "str">')
            invoice = self.env['account.move.receptor'].create({
                'currency_id': 39,
                'temp_name': xml_name,
                'xml_temp': base64.encodebytes(data)

            })
            _logger.info('E-INV-RECEPT TIR - Se creó el fichero temporal')
        try:
            _logger.info('E-INV-RECEPT TIR - Leyendo XML')
            invoice_xml = etree.fromstring(base64.b64decode(invoice.xml_temp))

            try:
                _logger.info('E-INV-RECEPT TIR - Buscando tipo de Documento')
                document_type = re.search('FacturaElectronica|NotaCreditoElectronica|NotaDebitoElectronica|TiqueteElectronico', invoice_xml.tag).group(0)

                if document_type == 'TiqueteElectronico':
                    raise UserError(_("This is a TICKET only invoices are valid for taxes"))
                if document_type in ('FacturaElectronica', 'NotaCreditoElectronica', 'NotaDebitoElectronica'):

                    if document_type == 'FacturaElectronica':
                        self.process_electronic_document(invoice_xml, invoice, 'FE')
                    if document_type == 'NotaCreditoElectronica':
                        self.process_electronic_document(invoice_xml, invoice, 'NC')
                    if document_type == 'NotaDebitoElectronica':
                        self.process_electronic_document(invoice_xml, invoice, 'ND')
            except:
                _logger.info('E-INV-RECEPT TIR - El XML puede ser un MR')
                self.process_mr(invoice_xml, invoice)


        except Exception as e:
            _logger.info('E-INV-RECEPT TIR - Ocurrió un error leyendo el archivo: ' + xml_name)

    def _extract_data_from_zip(self, url, response, file_name=None):
        """
        :return bytes: return read bytes

        :param response: response object
        :param url: url of zip file
        :param file_name: the file name to be extracted from the given url
        """
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        file = ''
        for file_path in archive.namelist():
            if file_name in file_path:
                file = file_path
                break
        try:
            return archive.open(file).read()
        except KeyError as e:
            _logger.info(e)
            return ''

    def process_zip(self, adjunto):
        lista = zipfile.ZipFile(io.BytesIO(adjunto.content))
        archivos = lista.namelist()

        for data in archivos:
            if ".pdf" in data or ".PDF" in data:
                pdf = self._extract_data_from_zip('', adjunto, data)
                pdf_name = data
        try:
            _logger.info('E-INV-RECEPT TIR - Verificando si el correo contenía un PDF')
            if pdf:
                for data in archivos:
                    if ".xml" in data or ".XML" in data:
                        xml = self._extract_data_from_zip('', adjunto, data)
                        xml_name = data
                        self.process_xml_pdf(xml, xml_name, pdf, pdf_name)

        except:
            _logger.info('E-INV-RECEPT TIR - El correo no contiene PDF')
            for data in archivos:
                if ".xml" in data or ".XML" in data:
                    xml = self._extract_data_from_zip('', adjunto, data)
                    xml_name = data
                    self.process_xml(xml, xml_name)

    @api.model
    def message_process_fe(self, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None):
        """ Process an incoming RFC2822 email message, relying on
            ``mail.message.parse()`` for the parsing operation,
            and ``message_route()`` to figure out the target model.

            Once the target model is known, its ``message_new`` method
            is called with the new message (if the thread record did not exist)
            or its ``message_update`` method (if it did).

           :param string model: the fallback model to use if the message
               does not match any of the currently configured mail aliases
               (may be None if a matching alias is supposed to be present)
           :param message: source of the RFC2822 message
           :type message: string or xmlrpclib.Binary
           :type dict custom_values: optional dictionary of field values
                to pass to ``message_new`` if a new record needs to be created.
                Ignored if the thread record already exists, and also if a
                matching mail.alias was found (aliases define their own defaults)
           :param bool save_original: whether to keep a copy of the original
                email source attached to the message after it is imported.
           :param bool strip_attachments: whether to strip all attachments
                before processing the message, in order to save some space.
           :param int thread_id: optional ID of the record/thread from ``model``
               to which this mail should be attached. When provided, this
               overrides the automatic detection based on the message
               headers.
        """
        # extract message bytes - we are forced to pass the message as binary because
        # we don't know its encoding until we parse its headers and hence can't
        # convert it to utf-8 for transport between the mailgate script and here.
        if isinstance(message, xmlrpclib.Binary):
            message = bytes(message.data)
        if isinstance(message, str):
            message = message.encode('utf-8')
        message = email.message_from_bytes(message, policy=email.policy.SMTP)

        # parse the message, verify we are not in a loop by checking message_id is not duplicated
        msg_dict = self.message_parse(message, save_original=save_original)

        adjuntos = msg_dict['attachments']

        for data in adjuntos:
            if ".pdf" in data.fname or ".PDF" in data.fname:
                pdf = data
        try:
            _logger.info('E-INV-RECEPT TIR - Verificando si el correo contenía un PDF')
            if pdf:
                for data in adjuntos:
                    if ".xml" in data.fname or ".XML" in data.fname:
                        self.process_xml_pdf(data.content, data.fname, pdf.content, pdf.fname)
            else:
                for data in adjuntos:
                    if ".xml" in data.fname or ".XML" in data.fname:
                        self.process_xml(data.content, data.fname)

        except:
            _logger.info('E-INV-RE process_xml TIR - El correo no contiene PDF')
            for data in adjuntos:
                if ".xml" in data.fname or ".XML" in data.fname:
                    self.process_xml(data.content, data.fname)

        for data in adjuntos:
            if ".zip" in data.fname or ".ZIP" in data.fname:
                self.process_zip(data)

        if strip_attachments:
            msg_dict.pop('attachments', None)

        existing_msg_ids = self.env['mail.message'].search([('message_id', '=', msg_dict['message_id'])], limit=1)
        if existing_msg_ids:
            _logger.info('Ignored mail from %s to %s with Message-Id %s: found duplicated Message-Id during processing',
                         msg_dict.get('email_from'), msg_dict.get('to'), msg_dict.get('message_id'))
            return False

        # find possible routes for the message
        routes = self.message_route(message, msg_dict, model, thread_id, custom_values)
        thread_id = self._message_route_process(message, msg_dict, routes)
        return thread_id
