# -*- coding: utf-8 -*-

from odoo import api, fields, models


class Cisa(models.Model):
    _name = "cisa"
    _description = "CISA"
    _order = "fch desc"

    name = fields.Char(string='Metodo')
    fch = fields.Datetime(string='Fecha')
    res = fields.Text(string='Respuesta')