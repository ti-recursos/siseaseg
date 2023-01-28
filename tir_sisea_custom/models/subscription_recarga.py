from odoo import fields, models, api, tools, _
from odoo.exceptions import UserError, ValidationError

import phonenumbers
from random import randint

import datetime
import pytz

class SaleSubscriptionNumber(models.Model):
    _name = 'sale.subscription.number'
    _description = 'Sale Subscription Number'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Number', required=True)

    subscription_id = fields.Many2one('sale.subscription', domain= [('stage_category', '=', 'progress')], string="Sale Subscription", required=True)

    partner_id = fields.Many2one('res.partner', string="Partner Assigned")

    user_id_encargado = fields.Many2one('res.users', copy=False, tracking=True, default=lambda self: self.env.user,
        string='Assigned User')

    def _compute_last_recharge(self):
        for number in self:
            if len(number.recharges_ids) > 0:
                dates = []
                for recharge in number.recharges_ids:
                    dates.append(recharge.date_recharge)
                number.last_recharge = max(dates)
            else:
                number.last_recharge = False

    def _compute_recharge(self):
        for number in self:
            if len(number.recharges_ids) > 0:
                now_utc = datetime.datetime.now(pytz.timezone('UTC'))
                ahora = datetime.datetime.strptime(now_utc.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")

                horas_minimas = 0
                recharges = 0
                for recharge in number.recharges_ids:
                    
                    then = datetime.datetime.combine(recharge.date_recharge, datetime.datetime.min.time())
                    diff = ahora - then
                    days, seconds = diff.days, diff.seconds
                    hours = days * 24 + seconds / 60
                    if horas_minimas == 0:
                        horas_minimas = hours
                        recharges = recharge.balance
                    if hours <= horas_minimas:
                        horas_minimas = hours
                        recharges = recharge.balance
                number.number_balance = recharges
            else:
                number.number_balance = False

    last_recharge = fields.Date(string='Last Recharge', compute=_compute_last_recharge)
    next_recharge = fields.Date(string='Next Recharge')



    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False, default=lambda self: self.env.company)
    currency_id = fields.Many2one(string='Company Currency', readonly=True,
        related='company_id.currency_id')
    number_balance = fields.Monetary(string='Balance', compute=_compute_recharge)

    recharges_ids = fields.One2many(
        'sale.subscription.number.line',
        'number_id',
        string='Recharges',tracking=True
    )

    def _default_category(self):
        return self.env['sale.subscription.number.category'].browse(self._context.get('category_id'))

    category_id = fields.Many2many('sale.subscription.number.category', column1='partner_id',
                                column2='category_id', string='Proveedor', default=_default_category)

    @api.onchange('name')
    def _onchange_phone(self):
        if self.name:
            phone = phonenumbers.parse(self.name, self.env.user.partner_id.country_id and self.env.user.partner_id.country_id.code or 'CR')
            valid = phonenumbers.is_valid_number(phone)
            if not valid:
                alert = {
                    'title': 'Atención',
                    'message': _('Número de teléfono inválido')
                }
                return {'value': {'name': ''}, 'warning': alert}
            else:
                formateado = phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                nombre = self.env['sale.subscription.number'].sudo().search([('name', '=', formateado)])
                if len(nombre) >= 1:
                    alert = {
                        'title': 'Atención',
                        'message': _('Número de teléfono inválido, ya existe en el sistema')
                    }
                    return {'value': {'name': ''}, 'warning': alert}
                else:
                    self.name = formateado

    @api.onchange('subscription_id')
    def onchange_subscription_id(self):
        for number in self:
            if len(number.subscription_id) > 0:
                number.partner_id = number.subscription_id.partner_id.id

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        for number in self:
            if number.partner_id:

                sub_ids = self.env['sale.subscription'].sudo().search([('partner_id', '=', number.partner_id.id)]).ids
                if len(sub_ids) > 0:
                    number.subscription_id = sub_ids[0]
                else:
                    self.subscription_id = False
    @api.model
    def create(self, vals):
        res = super(SaleSubscriptionNumber, self).create(vals)
        if 'next_recharge' in vals:
            res.action_recharge()
        return res

    def write(self, vals):
        res = super(SaleSubscriptionNumber, self).write(vals)
        if 'next_recharge' in vals:
            self.action_recharge()
        return res

    def action_recharge(self):
        for number in self:
            res_model_id = self.env['ir.model'].sudo().search([('model', '=', 'sale.subscription.number')])

            self.env['mail.activity'].sudo().create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': 'Recargar Contrato #' + number.subscription_id.code,
                'res_name': number.name,
                'note': '<p>Recordar recargar la SIM</p>',
                'res_id': number.id,
                'res_model': 'sale.subscription.number',
                'res_model_id': res_model_id.id,
                'date_deadline': number.next_recharge,
                'user_id': number.user_id_encargado.id,
            })
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito en operación!'),
                'message': 'Se programó el recordatorio',
                'sticky': True,
                'type':'success',
            }
        }
        return notification


class SaleSubscriptionNumberLine(models.Model):
    _name = "sale.subscription.number.line"
    _description = "Camaras Contrato"


    number_id = fields.Many2one(
        comodel_name='sale.subscription.number',
        string='Documento'
    )

    date_recharge = fields.Date(string='Recharge Date', default=fields.Date.today)
    recharge_user_id = fields.Many2one('res.users', copy=False, tracking=True, default=lambda self: self.env.user,
        string='Assigned User')

    tipo_operacion = fields.Selection(string='Operación', selection=[('consulta', 'Consulta'), ('recarga', 'Recarga')])
    

    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False, default=lambda self: self.env.company)
    currency_id = fields.Many2one(string='Company Currency', readonly=True,
        related='company_id.currency_id')
    balance = fields.Monetary(string='Balance')
    
class NumberCategory(models.Model):
    _description = 'Number Tags'
    _name = 'sale.subscription.number.category'
    _order = 'name'
    _parent_store = True

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color Index', default=_get_default_color)
    parent_id = fields.Many2one('sale.subscription.number.category', string='Parent Category', index=True, ondelete='cascade')
    child_ids = fields.One2many('sale.subscription.number.category', 'parent_id', string='Child Tags')
    active = fields.Boolean(default=True, help="The active field allows you to hide the category without removing it.")
    parent_path = fields.Char(index=True)
    partner_ids = fields.Many2many('sale.subscription.number', column1='category_id', column2='partner_id', string='Partners')

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You can not create recursive tags.'))

    def name_get(self):
        """ Return the categories' display name, including their direct
            parent by default.
            If ``context['partner_category_display']`` is ``'short'``, the short
            version of the category name (without the direct parent) is used.
            The default is the long version.
        """
        if self._context.get('partner_category_display') == 'short':
            return super(NumberCategory, self).name_get()

        res = []
        for category in self:
            names = []
            current = category
            while current:
                names.append(current.name)
                current = current.parent_id
            res.append((category.id, ' / '.join(reversed(names))))
        return res

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name:
            # Be sure name_search is symetric to name_get
            name = name.split(' / ')[-1]
            args = [('name', operator, name)] + args
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)