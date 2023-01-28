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

"""
Se encarga de leer los archivos que respodne el banco
"""

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

    def process_csv_bank(self, data, csv_name, id_bank):
        if str(type(data)) in "<class 'str'>":
            _logger.info('E-INV-RECEPT TIR - El documento es de tipo <class "str">')
            a = str(data).encode('ascii', errors='ignore').decode()
            message_bytes = a.encode('utf8')
            attachment = self.env['automatic.charge.bank.line'].sudo().create({
                'bank_charge_id': id_bank,
                'name': csv_name,
                'file_data': base64.encodebytes(message_bytes),


            })
            _logger.info('E-INV-RECEPT TIR - Se creó el fichero temporal')
        elif str(type(data)) in "<class 'bytes'>":
            _logger.info('E-INV-RECEPT TIR - El documento es de tipo <class "str">')
            attachment = self.env['automatic.charge.bank.line'].sudo().create({
                'bank_charge_id': id_bank,
                'name': csv_name,
                'file_data': base64.encodebytes(data),


            })
            _logger.info('E-INV-RECEPT TIR - Se creó el fichero temporal')

    @api.model
    def message_process_bank(self, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None):
        _logger.error('message_process_bank de TIR SISEA')
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

        now_utc = datetime.datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        dia = now_cr.strftime('%d')  # '%02d' % now_cr.day,
        mes = now_cr.strftime('%m')  # '%02d' % now_cr.month,
        anno = now_cr.strftime('%Y')  # str(now_cr.year)[2:4],
        date_cr = now_cr.strftime(anno + "-" + mes + "-" + dia + " %H:%M:%S")

        id_bank = self.env['automatic.charge.bank'].sudo().create({
            'name': msg_dict['subject'] + " " + date_cr,
            'company_id': self.env.user.company_id.id,
            'date_doc': now_utc,
        })
        # Guardo los archivos xlsx y txt del correo
        for data in adjuntos:
            if '.xlsx' in data.fname:
                csv_name = data.fname
                self.process_csv_bank(data.content, csv_name, id_bank.id)
            if '.txt' in data.fname:
                csv_name = data.fname
                self.process_csv_bank(data.content, csv_name, id_bank.id)

        id_bank.read_lines()

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
