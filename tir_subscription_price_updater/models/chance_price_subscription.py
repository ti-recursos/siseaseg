# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import date_utils

import json
from datetime import datetime
import pytz
import io


try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

class UpdatePrices(models.Model):
    _name = 'sale.subscription.update.price'
    _description = 'Update Prices'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Document Reference', required=True, copy=False, readonly=True, states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    domain = fields.Text(default='[]', states={'draft': [('readonly', False)]}, readonly=True, required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False, default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one(string='Company Currency', readonly=True, related='company_id.currency_id', tracking=True)
    amount_increases = fields.Monetary(string='Amount That Increases', readonly=True, compute="_compute_amount_increases")
    amount_total = fields.Monetary(string='Balance', required=True, readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    # product_id = fields.Many2one(comodel_name='product.product', string='Product', readonly=True, required=True, states={'draft': [('readonly', False)]}, tracking=True)
    product_ids = fields.Many2many(
        'product.product', 'product_updater_id', 'id', 'product_ids',
        string="Products",
        domain="[('recurring_invoice', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')

    line_ids = fields.One2many(
        'sale.subscription.update.price.lines',
        'model_id',
        string='Update Prices Lines'
    )

    def _compute_amount_increases(self):
        for record in self:
            amount_increases = 0.0

            if record.line_ids:
                for line_update in record.line_ids:
                    if line_update.to_update:
                        for sub_line in line_update.sale_subscription.recurring_invoice_line_ids:
                            for product_line in record.product_ids:
                                if sub_line.product_id.product_tmpl_id.id == product_line.product_tmpl_id.id:
                                    amount_increases += record.amount_total

            record.amount_increases = amount_increases

    def action_get_preview(self):
        for record in self:
            subscriptions = self.env['sale.subscription'].sudo().search(eval(record.domain))
            record.sudo().line_ids = False
            for sub in subscriptions:
                amount_product = 0.0
                aumento = 0.0
                for line in sub.recurring_invoice_line_ids:
                    for product_line in record.product_ids:
                        if line.product_id.product_tmpl_id.id == product_line.product_tmpl_id.id:
                            amount_product += line.price_unit * line.quantity
                            aumento += record.amount_total
                new_amount = sub.recurring_total + aumento
                record.sudo().line_ids = [(0, 0, {
                    'model_id': record.id,
                    'sale_subscription': sub.id,
                    'recurring_total': sub.recurring_total,
                    'product_amount': amount_product,
                    'amount_total': new_amount
                })]
    
    def action_update_prices(self):
        for record in self:
            count = 0
            for line in record.line_ids:
                if line.to_update:
                    for sub_line in line.sale_subscription.recurring_invoice_line_ids:
                        for product_line in record.product_ids:
                            if sub_line.product_id.product_tmpl_id.id == product_line.product_tmpl_id.id:
                                sub_line.price_unit = sub_line.price_unit + record.amount_total
                    count += 1
                    line.state = 'done'
            record.state = 'done'
            msg_body = (_('Se actualizaron los precios a un total de: %s suscripciones') % count)
            record.message_post(body=msg_body)

    def action_confirm(self):
        self.state = 'confirm'
        for record in self.line_ids:
            if record.to_update:
                record.state = 'confirm'
            else:
                record.state = 'cancel'

    def action_cancel(self):
        self.state = 'cancel'
        for record in self.line_ids:
            record.state = 'cancel'

    def unlink(self):
        for order in self:
            if order.state not in ('draft'):
                raise UserError(_('You can not delete a record.'))
        return super(UpdatePrices, self).unlink()

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('subscription.update') or _('New')
        result = super(UpdatePrices, self).create(vals)
        return result

    def report_lines_xls(self):
        now_utc = datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        dia = '%02d' % now_cr.day
        mes = '%02d' % now_cr.month
        anno = str(now_cr.year)[2:4]

        date_cr = now_cr.strftime("20" + anno + "-" + str(mes) + "-" + str(dia) + "T%H:%M:%S-06:00")
        data = {
            'ids': self.ids,
            'model': self._name,
            'record': self.id
        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'sale.subscription.update.price',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Actualización de suscripciones - ' + date_cr,
                     },
            'report_type': 'xlsx'
        }
        
    def get_xlsx_report(self, data, response):

        lineas = self.env['sale.subscription.update.price'].sudo().search([('id', '=', data['record'])], limit=1).line_ids

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        sheet = workbook.add_worksheet("Subscription Resume")
        format2 = workbook.add_format({'font_size': 12, 'bold': True, 'bg_color': '#714B67', 'font_color': 'white'})
        format3 = workbook.add_format({'font_size': 10})
        format4 = workbook.add_format({'font_size': 10, 'num_format': '₡#,##0.00'})


        sheet.write(2, 0, 'Cliente', format2)
        sheet.write(2, 1, 'Contrato', format2)
        sheet.write(2, 2, 'Fecha de inicio', format2)
        sheet.write(2, 3, 'Monto de la suscripción', format2)
        sheet.write(2, 4, 'Monto del Producto', format2)
        sheet.write(2, 5, 'Monto Actualizado', format2)
        sheet.write(2, 6, 'Actualizar', format2)
        
        row = 3
        for record in lineas:
            sheet.write(row, 0, record.name.name, format3)
            sheet.write(row, 1, record.sale_subscription.code, format3)
            sheet.write(row, 2, record.date_start.strftime("%d-%m-%Y"), format3)
            sheet.write(row, 3, record.recurring_total, format4)
            sheet.write(row, 4, record.product_amount, format4)
            sheet.write(row, 5, record.amount_total, format4)
            sheet.write(row, 6, record.to_update, format4)
            row += 1

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

class UpdatePricesLines(models.Model):
    _name = 'sale.subscription.update.price.lines'
    _description = 'Update Prices Lines'

    model_id = fields.Many2one(
        comodel_name='sale.subscription.update.price',
        string='Update Prices'
    )

    name = fields.Many2one('res.partner', string="Partner", related='sale_subscription.partner_id', readonly=True)
    sale_subscription = fields.Many2one('sale.subscription', string="Contract", required=True, readonly=True)
    date_start = fields.Date(string='Date Start', related='sale_subscription.date_start', readonly=True)
    
    currency_id = fields.Many2one(string='Currency', related='sale_subscription.currency_id', readonly=True)
    recurring_total = fields.Float(string='Amount Subscription', readonly=True)
    product_amount = fields.Monetary(string='Product Amount', readonly=True)
    amount_total = fields.Monetary(string='Amount Updated', readonly=True)
    
    to_update = fields.Boolean(string='To Update', default=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')
    """
    def _compute_amount_total(self):
        for record in self:
            if not record.to_update:
                record.sudo().amount_total = record.recurring_total
            else:
                amount_product = 0.0
                for line in record.sale_subscription.recurring_invoice_line_ids:
                    if line.product_id.product_tmpl_id.id == record.model_id.product_id.product_tmpl_id.id:
                        amount_product += line.price_unit * line.quantity
                new_amount = (record.recurring_total - amount_product) + record.model_id.amount_total
                record.sudo().amount_total = new_amount
    """
