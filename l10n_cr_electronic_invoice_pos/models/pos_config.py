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

class POSConfig(models.Model):
    _inherit = 'pos.config'
    _description = "Excluir impuesto servicio"

    exclude_tax = fields.Boolean(string='Control de Impuesto de Servicio')