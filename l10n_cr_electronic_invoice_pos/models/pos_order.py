import logging
from datetime import timedelta
from functools import partial

import psycopg2
import pytz

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero, float_round
from odoo.exceptions import ValidationError, UserError
from odoo.http import request
from odoo.osv.expression import AND
import base64

_logger = logging.getLogger(__name__)

class POSPaymentMethods(models.Model):
    _inherit = 'pos.payment.method'
    _description = "Métodos de pago POS"

    sequence = fields.Char(string="Sequence", required=False,  index=False)


class PosOrder(models.Model):
    _inherit = "pos.order"
    _description = "Pedidos Punto de Venta"

    def _prepare_invoice_vals(self):

        # Tipo de Documento
        if self.partner_id.vat and self.partner_id.identification_id:
            tipo_doc = 'FE'
        else:
            tipo_doc = 'TE'

        self.ensure_one()

        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')

        pago = self.env['pos.payment'].search([('pos_order_id', '=', self.id)], limit=1)

        payment_methods = self.env['payment.methods'].search([('sequence', '=', pago.payment_method_id.sequence)], limit=1)

        if payment_methods:
            vals = {
                'payment_reference': self.name,
                'invoice_origin': self.name,
                'journal_id': self.session_id.config_id.invoice_journal_id.id,
                'move_type': 'out_invoice' if self.amount_total >= 0 else 'out_refund',
                'tipo_documento': tipo_doc,
                'payment_methods_id': payment_methods,
                'ref': self.name,
                'partner_id': self.partner_id.id,
                'narration': self.note or '',
                # considering partner's sale pricelist's currency
                'currency_id': self.pricelist_id.currency_id.id,
                'company_id': self.company_id,
                'invoice_user_id': self.user_id.id,
                'invoice_date': self.date_order.astimezone(timezone).date(),
                'fiscal_position_id': self.fiscal_position_id.id,
                'invoice_line_ids': [(0, None, self._prepare_invoice_line(line)) for line in self.lines],
                'invoice_cash_rounding_id': self.config_id.rounding_method.id if self.config_id.cash_rounding else False
            }
        else:
            vals = {
                'payment_reference': self.name,
                'invoice_origin': self.name,
                'journal_id': self.session_id.config_id.invoice_journal_id.id,
                'move_type': 'out_invoice' if self.amount_total >= 0 else 'out_refund',
                'payment_methods_id': self.partner_id.payment_methods_id,
                'tipo_documento': tipo_doc,
                'ref': self.name,
                'partner_id': self.partner_id.id,
                'narration': self.note or '',
                'company_id': self.company_id,
                # considering partner's sale pricelist's currency
                'currency_id': self.pricelist_id.currency_id.id,
                'invoice_user_id': self.user_id.id,
                'invoice_date': self.date_order.astimezone(timezone).date(),
                'fiscal_position_id': self.fiscal_position_id.id,
                'invoice_line_ids': [(0, None, self._prepare_invoice_line(line)) for line in self.lines],
                'invoice_cash_rounding_id': self.config_id.rounding_method.id if self.config_id.cash_rounding else False
            }
        return vals

    def action_pos_order_invoice(self):
        for order in self:
            if not order.partner_id:
                raise UserError(_('Please provide a partner for the sale.'))

            move_vals = order._prepare_invoice_vals()
            new_move = self.env['account.move'].create(move_vals)
            order.write({'account_move': new_move.id, 'state': 'invoiced'})
            company = self.env['res.company'].search([('id', '=', order.company_id.id)])
            new_move.economic_activity_id = company.activity_id
            new_move.action_post()

            message = _("This invoice has been created from the point of sale session: <a href=# data-oe-model=pos.order data-oe-id=%d>%s</a>") % (order.id, order.name)
            new_move.message_post(body=message)


            order.write({'account_move': new_move.id, 'state': 'invoiced'})