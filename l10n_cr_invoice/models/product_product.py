# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

import requests
from datetime import datetime
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ProductProductElectronic(models.Model):
    _inherit = "product.product"