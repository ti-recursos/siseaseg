from odoo import fields, models, api, tools, _
from odoo.exceptions import UserError
from cryptography.fernet import Fernet

import datetime
import pytz
from time import strftime, gmtime

import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'
    _description = 'Company Information'

    tir_key = fields.Char(string="Key Company", required=False)
    nr_afiliado = fields.Char(string="Affiliate Number", required=False)

    tolerancia_documentos = fields.Integer(string='Total Unpaid Documents')

    def create_key(self):
        key = Fernet.generate_key()
        self.tir_key = key
        _logger.error('tir_sisea_custom - KEY Fernet: %s', str(key))