# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import email
import logging
import os

from lxml import etree

from odoo.tests import Form
from xmlrpc import client as xmlrpclib

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FetchmailServer(models.Model):

    _inherit = 'fetchmail.server'

    invoice_receptor = fields.Boolean(string="Receptor de Facturación", required=False, default=False)
    company_id = fields.Many2one(
        'res.company', "Company", default=lambda self: self.env.company, required=True)

    def fetch_mail(self):
        """ WARNING: meant for cron usage only - will commit() after each email! """
        additionnal_context = {
            'fetchmail_cron_running': True
        }
        MailThread = self.env['mail.thread']
        for server in self:
            _logger.info('start checking for new emails on %s server %s', server.server_type, server.name)
            additionnal_context['default_fetchmail_server_id'] = server.id
            count, failed = 0, 0
            imap_server = None
            pop_server = None
            if server.server_type == 'imap':
                try:
                    imap_server = server.connect()
                    imap_server.select()
                    result, data = imap_server.search(None, '(UNSEEN)')
                    for num in data[0].split():
                        res_id = None
                        result, data = imap_server.fetch(num, '(RFC822)')
                        imap_server.store(num, '-FLAGS', '\\Seen')
                        try:
                            if server.invoice_receptor:
                                res_id = MailThread.with_context(**additionnal_context).message_process_fe(
                                    server.object_id.model, data[0][1], save_original=server.original,
                                    strip_attachments=(not server.attach))
                            else:
                                res_id = MailThread.with_context(**additionnal_context).message_process(
                                    server.object_id.model, data[0][1], save_original=server.original,
                                    strip_attachments=(not server.attach))
                        except Exception:
                            _logger.info('Failed to process mail from %s server %s.', server.server_type, server.name, exc_info=True)
                            failed += 1
                        imap_server.store(num, '+FLAGS', '\\Seen')
                        self._cr.commit()
                        count += 1
                    _logger.info("Fetched %d email(s) on %s server %s; %d succeeded, %d failed.", count, server.server_type, server.name, (count - failed), failed)
                except Exception:
                    _logger.info("General failure when trying to fetch mail from %s server %s.", server.server_type, server.name, exc_info=True)
                finally:
                    if imap_server:
                        imap_server.close()
                        imap_server.logout()
            elif server.server_type == 'pop':
                try:
                    while True:
                        pop_server = server.connect()
                        (num_messages, total_size) = pop_server.stat()
                        pop_server.list()
                        for num in range(1, min(MAX_POP_MESSAGES, num_messages) + 1):
                            (header, messages, octets) = pop_server.retr(num)
                            message = (b'\n').join(messages)
                            res_id = None
                            try:
                                if server.invoice_receptor:
                                    res_id = MailThread.with_context(**additionnal_context).message_process_fe(
                                        server.object_id.model, message, save_original=server.original,
                                        strip_attachments=(not server.attach))
                                else:
                                    res_id = MailThread.with_context(**additionnal_context).message_process(
                                        server.object_id.model, message, save_original=server.original,
                                        strip_attachments=(not server.attach))
                                pop_server.dele(num)
                            except Exception:
                                _logger.info('Failed to process mail from %s server %s.', server.server_type, server.name, exc_info=True)
                                failed += 1
                            self.env.cr.commit()
                        if num_messages < MAX_POP_MESSAGES:
                            break
                        pop_server.quit()
                        _logger.info("Fetched %d email(s) on %s server %s; %d succeeded, %d failed.", num_messages, server.server_type, server.name, (num_messages - failed), failed)
                except Exception:
                    _logger.info("General failure when trying to fetch mail from %s server %s.", server.server_type, server.name, exc_info=True)
                finally:
                    if pop_server:
                        pop_server.quit()
            server.write({'date': fields.Datetime.now()})
        return True
