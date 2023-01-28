# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AutEx(models.Model):
    _name = "aut.ex"
    _description = "Auth Ex"

    active = fields.Boolean(string="Active", required=False, default=True)
    code = fields.Char(string="Code", required=False, )
    name = fields.Char(string="Name", required=False, )
