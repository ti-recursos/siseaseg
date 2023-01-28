import logging
from datetime import datetime, timedelta
from collections import defaultdict
from functools import partial
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import format_date, float_compare
from odoo.tools.float_utils import float_is_zero
from odoo.tools.misc import get_lang


_logger = logging.getLogger(__name__)


class SaleOrderSISEA(models.Model):
    _inherit = "sale.order"
    _description = "Sale Order"

    installation_ids = fields.One2many(
        'sale.order.installation',
        'order_id',
        string='Installation Lines'
    )
    processed = fields.Boolean(string="Processed", default=False)

    contract_id = fields.Char(string="Contract")

    @api.onchange('opportunity_id')
    def oportunity_id_changed(self):
        for sale in self:
            if sale.opportunity_id.contract:
                sale.contract_id = sale.opportunity_id.contract

    def _get_stock_type_ids(self):
        data = self.env['stock.picking.type'].search([])

        if self._context.get('default_move_type') == 'out_invoice':
            for line in data:
                if line.code == 'outgoing':
                    return line
        if self._context.get('default_move_type') == 'in_invoice':
            for line in data:
                if line.code == 'incoming':
                    return line

    picking_count = fields.Integer(string="Count", compute="_count_picking")
    invoice_picking_id = fields.Many2one('stock.picking', string="Picking Id")

    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type',
                                      default=_get_stock_type_ids,
                                      help="This will determine picking type of incoming shipment")

    def _count_picking(self):
        for order in self:
            total = self.env['stock.picking'].sudo().search([('contract', '=', order.contract_id)])
            if len(total) > 0:
                order.picking_count = len(total)
            else:
                order.picking_count = 0

    def action_cancel(self):
        res = super(SaleOrderSISEA, self).action_cancel()
        # Indico que no se ha generado la salida de inventario para la instalación
        self.processed = False
        # En caso que tenga una orden de salida de inventario para la instalación, se debe reversar
        if self.invoice_picking_id:
            self._reverse_moves()
            self.picking_type_id = False
            self.invoice_picking_id = False
            self.picking_count = 0
        return res

    def action_stock_move(self):
        lineas = 0
        for linea in self.installation_ids:
            lineas = lineas + 1

        if lineas == 0:
            raise UserError(('Este documento no contiene líneas de producto para la instalación'))
        pick = {}
        if self.picking_type_id.code == 'outgoing':
            pick = {
                'picking_type_id': self.picking_type_id.id,
                'partner_id': self.partner_id.id,
                'origin': self.name,
                'location_dest_id': self.partner_id.property_stock_customer.id,
                'location_id': self.picking_type_id.default_location_src_id.id,
                'move_type': 'direct',
                'contract': self.contract_id or False
            }
        if self.picking_type_id.code == 'incoming':
            pick = {
                'picking_type_id': self.picking_type_id.id,
                'partner_id': self.partner_id.id,
                'origin': self.name,
                'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                'location_id': self.partner_id.property_stock_supplier.id,
                'move_type': 'direct',
                'contract': self.contract_id or False
            }

        picking = self.env['stock.picking'].create(pick)
        self.invoice_picking_id = picking.id
        #self.picking_count = len(picking)
        moves = self.installation_ids.filtered(
            lambda r: r.product_id.type in ['product', 'consu'])._create_stock_moves(picking)
        move_ids = moves._action_confirm()
        move_ids._action_assign()
        self.processed = True


    def action_view_picking(self):
        action = self.env.ref('stock.action_picking_tree_ready')
        result = action.read()[0]
        result.pop('id', None)
        result['context'] = {}
        result['domain'] = [('contract', '=', self.contract_id)]
        pick_ids = self.env['stock.picking'].sudo().search([('contract', '=', self.contract_id)])

        form = self.env.ref('stock.view_picking_form', False)
        tree = self.env.ref('stock.vpicktree', False)
        result['views'] = [(tree.id or False, 'tree'), (form.id or False, 'form')]
        result['res_id'] = pick_ids or False
        return result

    def _reverse_moves(self, default_values_list=None, cancel=False):
        ''' Reverse a recordset of account.move.
        If cancel parameter is true, the reconcilable or liquidity lines
        of each original move will be reconciled with its reverse's.

        :param default_values_list: A list of default values to consider per move.
                                    ('type' & 'reversed_entry_id' are computed in the method).
        :return:                    An account.move recordset, reverse of the current self.
        '''

        if self.picking_type_id.code == 'outgoing':
            data = self.env['stock.picking.type'].search(
                [('company_id', '=', self.company_id.id), ('code', '=', 'incoming')], limit=1)
            self.picking_type_id = data.id
        elif self.picking_type_id.code == 'incoming':
            data = self.env['stock.picking.type'].search(
                [('company_id', '=', self.company_id.id), ('code', '=', 'outgoing')], limit=1)
            self.picking_type_id = data.id


    def _create_invoices(self, grouped=False, final=False, date=None):

        res = super(SaleOrderSISEA, self)._create_invoices()

        for invoice in res:
            if invoice.partner_id.payment_methods_id:
                invoice.payment_methods_id = invoice.partner_id.payment_methods_id.id
                invoice.economic_activity_id = invoice.company_id.activity_id.id
                if invoice.invoice_date:
                    invoice.periodo_sub = invoice.invoice_date
                else:
                    invoice.periodo_sub = invoice.date

        return res

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal = self.env['account.move'].with_context(default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (self.company_id.name, self.company_id.id))

        invoice_vals = {
            'ref': self.client_order_ref or '',
            'move_type': 'out_invoice',
            'narration': self.note,
            'currency_id': self.pricelist_id.currency_id.id,
            'campaign_id': self.campaign_id.id,
            'medium_id': self.medium_id.id,
            'source_id': self.source_id.id,
            'invoice_user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id.get_fiscal_position(self.partner_invoice_id.id)).id,
            'partner_bank_id': self.company_id.partner_id.bank_ids[:1].id,
            'journal_id': journal.id,  # company comes from the journal
            'invoice_origin': (self.contract_id or self.name),
            'invoice_payment_term_id': self.payment_term_id.id,
            'payment_reference': self.reference,
            'transaction_ids': [(6, 0, self.transaction_ids.ids)],
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals

    @api.onchange('contract_id')
    def onchange_contract_id(self):
        if "" != self.contract_id and self.contract_id != False:
            contrato = self.contract_id
            if " " in contrato:
                self.contract_id = contrato.replace(" ", "")


class SaleOrderLine(models.Model):
    _name = "sale.order.installation"
    _description = 'Sales Order Line'

    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, ondelete='cascade', index=True,
                               copy=False)
    name = fields.Text(string='Description', required=True)

    product_id = fields.Many2one(
        'product.product', string='Product',
        domain="[('sale_ok','=',True)]", required=True)
    analytic_account_id = fields.Many2one('sale.order', string='Order', ondelete='cascade')
    company_id = fields.Many2one('res.company', related='analytic_account_id.company_id', store=True, index=True)
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(string='Quantity', help="Quantity that will be invoiced.", default=1.0,
                            digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True,
                             domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)
    price_unit = fields.Float(string='Unit Price', required=True, digits='Product Price')
    discount = fields.Float(string='Discount (%)', digits='Discount')
    price_subtotal = fields.Float(compute='_compute_amount', string='Subtotal', digits='Account', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related='analytic_account_id.currency_id', store=True)

    def _create_stock_moves(self, picking):
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        for line in self:
            price_unit = line.price_unit
            if picking.picking_type_id.code == 'outgoing':
                template = {
                    'name': line.name or '',
                    'product_id': line.product_id.id,
                    'product_uom': line.uom_id.id,
                    'location_id': picking.picking_type_id.default_location_src_id.id,
                    'location_dest_id': line.order_id.partner_id.property_stock_customer.id,
                    'picking_id': picking.id,
                    'state': 'draft',
                    'company_id': line.order_id.company_id.id,
                    'price_unit': price_unit,
                    'picking_type_id': picking.picking_type_id.id,
                    'route_ids': 1 and [
                        (6, 0, [x.id for x in self.env['stock.location.route'].search([('id', 'in', (2, 3))])])] or [],
                    'warehouse_id': picking.picking_type_id.warehouse_id.id,
                }
            if picking.picking_type_id.code == 'incoming':
                template = {
                    'name': line.name or '',
                    'product_id': line.product_id.id,
                    'product_uom': line.uom_id.id,
                    'location_id': line.order_id.partner_id.property_stock_supplier.id,
                    'location_dest_id': picking.picking_type_id.default_location_dest_id.id,
                    'picking_id': picking.id,
                    'state': 'draft',
                    'company_id': line.order_id.company_id.id,
                    'price_unit': price_unit,
                    'picking_type_id': picking.picking_type_id.id,
                    'route_ids': 1 and [
                        (6, 0, [x.id for x in self.env['stock.location.route'].search([('id', 'in', (2, 3))])])] or [],
                    'warehouse_id': picking.picking_type_id.warehouse_id.id,
                }
            diff_quantity = line.quantity
            tmp = template.copy()
            tmp.update({
                'product_uom_qty': diff_quantity,
            })
            template['product_uom_qty'] = diff_quantity
            done += moves.create(template)
        return done

    @api.depends('quantity', 'discount', 'price_unit', 'analytic_account_id.pricelist_id', 'uom_id', 'company_id')
    def _compute_amount(self):
        """
        Compute the amounts of the Subscription line.
        """
        AccountTax = self.env['account.tax']
        for line in self:
            price = AccountTax._fix_tax_included_price_company(line.price_unit, line.product_id.sudo().taxes_id,
                                                               AccountTax, line.company_id)
            price_subtotal = line.quantity * price * (100.0 - line.discount) / 100.0
            if line.analytic_account_id.pricelist_id.sudo().currency_id:
                price_subtotal = line.analytic_account_id.pricelist_id.sudo().currency_id.round(price_subtotal)
            line.update({
                'price_subtotal': price_subtotal,
            })

    @api.onchange('product_id')
    def onchange_product_id(self):
        product = self.product_id
        partner = self.analytic_account_id.partner_id
        if partner.lang:
            product = product.with_context(lang=partner.lang)

        self.name = product.get_product_multiline_description_sale()
        self.uom_id = product.uom_id.id

    @api.onchange('product_id', 'quantity')
    def onchange_product_quantity(self):
        if not self.product_id:
            self.price_unit = 0.0
        else:
            subscription = self.analytic_account_id

            self = self.with_company(subscription.company_id)
            product = self.product_id.with_context(
                pricelist=subscription.pricelist_id.id,
                quantity=self.quantity,
            )
            self.price_unit = product.price

            if not self.uom_id or product.uom_id.category_id.id != self.uom_id.category_id.id:
                self.uom_id = product.uom_id.id
            if self.uom_id.id != product.uom_id.id:
                self.price_unit = product.uom_id._compute_price(self.price_unit, self.uom_id)

    @api.onchange('uom_id')
    def onchange_uom_id(self):
        if not self.uom_id:
            self.price_unit = 0.0
        else:
            return self.onchange_product_quantity()

    def get_template_option_line(self):
        """ Return the account.analytic.invoice.line.option which has the same product_id as
        the invoice line"""
        if not self.analytic_account_id and not self.analytic_account_id.template_id:
            return False
        template = self.analytic_account_id.template_id
        return template.sudo().subscription_template_option_ids.filtered(lambda r: r.product_id == self.product_id)

    def _amount_line_tax(self):
        self.ensure_one()
        val = 0.0
        product = self.product_id
        product_tmp = product.sudo().product_tmpl_id
        for tax in product_tmp.taxes_id.filtered(lambda t: t.company_id == self.analytic_account_id.company_id):
            fpos_obj = self.env['account.fiscal.position']
            partner = self.analytic_account_id.partner_id
            fpos = fpos_obj.with_company(self.analytic_account_id.company_id).get_fiscal_position(partner.id)
            tax = fpos.map_tax(tax, product, partner)
            compute_vals = tax.compute_all(self.price_unit * (1 - (self.discount or 0.0) / 100.0),
                                           self.analytic_account_id.currency_id, self.quantity, product, partner)[
                'taxes']
            if compute_vals:
                val += compute_vals[0].get('amount', 0)
        return val

    @api.model
    def create(self, values):
        if values.get('product_id') and not values.get('name'):
            line = self.new(values)
            line.onchange_product_id()
            values['name'] = line._fields['name'].convert_to_write(line['name'], line)
        return super(SaleOrderLine, self).create(values)
