import logging
from datetime import datetime, timedelta


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    contract = fields.Char(string="Contract")