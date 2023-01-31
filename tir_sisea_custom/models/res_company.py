from odoo import fields, models, api, tools, _
from odoo.exceptions import UserError
from cryptography.fernet import Fernet

import requests
import json
import datetime
import pytz
from time import strftime, gmtime

import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'
    _description = 'Company Information'

    tir_key = fields.Char(string="Key Company", required=False)
    nr_afiliado = fields.Char(string="Affiliate Number", required=False, tracking=True)

    tolerancia_documentos = fields.Integer(string='Total Unpaid Documents', tracking=True)

    url_laro_automatic_charge = fields.Char(tracking=True)
    url_laro_token = fields.Char(tracking=True)
    id_laro = fields.Char(string='ID Laro Solutions', tracking=True)
    token_laro = fields.Char(string='TOKEN Laro Solutions', tracking=True)
    last_token_laro = fields.Datetime(tracking=True)

    def update_laro_token(self):
        companies = self.env['res.company'].sudo().search([])
        for company in companies:
            data = {
                'IDUser': company.id_laro,
                'Token': company.token_laro
            }
            url_laro = company.url_laro_token
            if url_laro[-1:] == '/':
                url_laro = url_laro[:-1]
            res_get = requests.get(url_laro, params=data)
            if res_get.status_code == 200:
                respuesta_dict = json.loads(res_get.text)
                if respuesta_dict.get('newToken'):
                    company.write(
                        {
                            'token_laro': respuesta_dict['newToken'],
                            'last_token_laro': fields.Datetime.now()
                        }
                    )

    def create_key(self):
        key = Fernet.generate_key()
        self.tir_key = key
        _logger.error('tir_sisea_custom - KEY Fernet: %s', str(key))