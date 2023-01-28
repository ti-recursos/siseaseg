# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleConditions(models.Model):
    _name = "sale.conditions"
    _description = "Sale Conditions"

    active = fields.Boolean(string="Active", required=False, default=True)
    code = fields.Char(string="Code", required=False, )
    sequence = fields.Char(string="Sequence", required=False,  index=False)
    name = fields.Char(string="Name", required=False, )
    notes = fields.Text(string="Notes", required=False, )
