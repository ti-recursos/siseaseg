# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

from datetime import datetime, time
from dateutil.relativedelta import relativedelta
from itertools import groupby
from pytz import timezone, UTC
from werkzeug.urls import url_encode

from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_is_zero
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang

import base64


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    _description = 'Purchase Order'

    move_receptor = fields.Many2one('account.move.receptor', string='Documento Receptor')

    def action_create_invoice(self):
        """Create the invoice associated to the PO.
                """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1) Prepare invoice vals and clean-up the section lines
        invoice_vals_list = []
        for order in self:
            if order.invoice_status != 'to invoice':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            invoice_vals = order._prepare_invoice()
            # Invoice line values (keep only necessary sections).
            for line in order.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue
                if not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    if pending_section:
                        invoice_vals['invoice_line_ids'].append((0, 0, pending_section._prepare_account_move_line()))
                        pending_section = None
                    invoice_vals['invoice_line_ids'].append((0, 0, line._prepare_account_move_line()))
            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(
                _('There is no invoiceable line. If a product has a control policy based on received quantity, please make sure that a quantity has been received.'))

        # 2) group by (company_id, partner_id, currency_id) for batch creation
        new_invoice_vals_list = []
        for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: (
        x.get('company_id'), x.get('partner_id'), x.get('currency_id'))):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None
            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])
            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)
        invoice_vals_list = new_invoice_vals_list

        # 3) Create invoices.
        moves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice')
        for vals in invoice_vals_list:
            moves |= AccountMove.with_company(vals['company_id']).create(vals)


        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        moves.filtered(
            lambda m: m.currency_id.round(m.amount_total) < 0).action_switch_invoice_into_refund_credit_note()

        # 5) Contiene Factura
        for move in moves:
            purchase_order = self.env['purchase.order'].sudo().search([('name', '=', move.invoice_origin)], limit=1)

            if purchase_order.move_receptor:
                move_receptor = purchase_order.move_receptor

                move.xml_supplier_approval = move_receptor.xml
                move.fname_xml_supplier_approval = move_receptor.name_xml

                if move_receptor.pdf_id:
                    message_description = '<p>Este documento está a la espera de su aprobación</p>'
                    move.message_post(body=message_description,
                                         attachments=[(move_receptor.pdf_id.name, base64.b64decode(move_receptor.pdf_id.datas))])
                else:
                    message_description = '<p>Este documento está a la espera de su aprobación</p>'

                    move.message_post(
                        body=message_description,
                        # subtype='mail.mt_note',
                        content_subtype='html')

                move_receptor.state = True
                move_receptor.documento_ref = move.id
                move_receptor.state_doc_ref = '1'
                move.load_xml_data()

                if move_receptor.tipo_documento == 'FE':
                    move.tipo_documento = 'FE'
                if move_receptor.tipo_documento == 'NC':
                    move.tipo_documento = 'NC'
                if move_receptor.tipo_documento == 'ND':
                    move.tipo_documento = 'NC'

        return self.action_view_invoice(moves)