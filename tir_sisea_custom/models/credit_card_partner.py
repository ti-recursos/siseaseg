from odoo import fields, models, api, tools, _
from odoo.exceptions import UserError
from cryptography.fernet import Fernet
import base64

import datetime
import pytz
from time import strftime, gmtime


class CreditCard(models.Model):
    _name = 'res.partner.cards'
    _description = 'Partner Credit Card Information'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=False)


    n_card = fields.Char(string="Credit Card Number Secure")
    date_due = fields.Char(string="Date Due Secure")

    view_n_card = fields.Char(string="Credit Card Number", required=True)
    view_date_due = fields.Char(string="Date Due", required=True)

    additional_info = fields.Char(string="Additional Information", required=False)
    partner_id = fields.Many2one('res.partner', string="Partner Assigned", required=True)

    lock = fields.Boolean(string="Lock Information", default=True)

    def _lock_cards(self):
        cards = self.env['res.partner.cards'].sudo().search([('lock', '=', False)])

        for card in cards:
            card.action_check()

    @api.onchange('additional_info')
    def additional_info_changed(self):
        if self.additional_info:
            if len(self.additional_info) > 36:
                raise UserError(_('The information must be less than 36 characters, you can correct it by:\n"' + str(self.additional_info)[:36] + '"'))

    @api.onchange('view_n_card')
    def n_card_changed(self):
        if self.view_n_card:
            if '-' in self.view_n_card:
                raise UserError(_('Por favor eliminar los guiones de la tarjeta'))
            elif len(self.view_n_card) != 16:
                raise UserError(_('Please validate the card number as it does not have the proper structure'))
            else:
                key = self.env.user.company_id.tir_key
                bk = self.view_n_card
                encrypt = self._encrypt(bk.encode(), key)
                self.view_n_card = "XXXX XXXX XXXX " + bk[12:]
                self.n_card = str(encrypt.decode())

    @api.onchange('view_date_due')
    def date_due_changed(self):
        if self.view_date_due:
            fecha = self.view_date_due

            if '/' in fecha:
                month, year = fecha.split('/')

                if len(month) != 2 and len(year) != 4:
                    raise UserError(_('The date is not in the proper format'))
                else:
                    key = self.env.user.company_id.tir_key
                    bk = self.view_date_due
                    encrypt = self._encrypt(bk.encode(), key)
                    self.view_date_due = "XX/XXXX"
                    self.date_due = str(encrypt.decode())
            else:
                raise UserError(_('The separator symbol is not the one indicated, it must be "/"'))


    def _encrypt(self, message: bytes, key: bytes) -> bytes:
        return Fernet(key).encrypt(message)

    def _decrypt(self, token: bytes, key: bytes) -> bytes:
        return Fernet(key).decrypt(token)

    def write(self, vals):
        if self.partner_id and vals.get('view_n_card') and self.lock:
            vals['name'] = self.partner_id.name + " " + self.view_n_card

        if self.partner_id and vals.get('view_n_card') and not self.lock:
            vals['name'] = self.partner_id.name + " " + "XXXX XXXX XXXX " + self.view_n_card[12:]
        res = super(CreditCard, self).write(vals)
        return res

    @api.model
    def create(self, vals_list):
        res = super(CreditCard, self).create(vals_list)

        if res.partner_id and res.view_n_card:
            res.name = res.partner_id.name + " " + res.view_n_card

        return res


    def action_check(self):
        if self.lock:
            key = self.env.user.company_id.tir_key
            tarjeta = str(self.n_card).encode('ascii', errors='ignore').decode()
            fecha = str(self.date_due).encode('ascii', errors='ignore').decode()


            self.view_n_card = self._decrypt(bytes(tarjeta, 'utf-8'), key)
            self.view_date_due = self._decrypt(bytes(fecha, 'utf-8'), key)

            self.lock = False

            # Se debe de notificar que se ha desbloqueado la información
            msg_body = _(
                'El usuario <a href=# data-oe-model=res.users data-oe-id=%d>%s</a> ha <strong>desbloqueado</strong> la información de la tarjeta') % (self.env.user.id, self.env.user.name)
            self.message_post(body=msg_body)

        else:
            bk = self.view_n_card
            self.view_n_card = "XXXX XXXX XXXX " + bk[12:]
            self.view_date_due = "XX/XXXX"

            self.lock = True
            # Se debe de notificar que se ha bloqueado la información
            msg_body = _(
                'El usuario <a href=# data-oe-model=res.users data-oe-id=%d>%s</a> ha <strong>bloqueado</strong> la información de la tarjeta') % (
                       self.env.user.id, self.env.user.name)
            self.message_post(body=msg_body)