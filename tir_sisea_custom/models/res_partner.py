# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, Warning
import phonenumbers
import logging
from datetime import datetime, date, timedelta

_logger = logging.getLogger(__name__)


class PartnerElectronic(models.Model):
    _inherit = "res.partner"

    contract_ids = installation_ids = fields.One2many(
        'sale.subscription',
        'partner_id',
        string='Partner Contracts'
    )