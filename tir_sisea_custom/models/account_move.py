
import logging

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import get_lang


import datetime
import pytz

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    proceso_gestion = fields.Boolean(string="Gestionando", default=False)

    gestion_line_ids = fields.One2many(
        'account.move.gestion.line',
        'move_id',
        string='Gestiones Realizadas',tracking=True
    )

    def action_gestion(self):
        for inv in self:
            self.env['account.move.gestion.line'].sudo().create({
                'move_id': inv.id,
                'fecha_gestion': datetime.datetime.now(pytz.timezone('UTC')),
                'gestion_user_id': self.env.user.id,
            })
            inv.proceso_gestion = True

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    _description = "Move Line"

    @api.constrains('product_uom_id')
    def _check_product_uom_category_id(self):
        pass
            
class AccountMoveGestion(models.Model):
    _name = "account.move.gestion.line"
    _description = "Lineas de Gestion de Contabilidad"


    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Documento'
    )

    fecha_gestion = fields.Date(string='Fecha de Gestión')
    comentario_gestion = fields.Text(string="Comentario Gestión")

    gestion_user_id = fields.Many2one('res.users', copy=False, tracking=True,
        string='Encargado de Gestión')

    def write(self, vals):
        if 'comentario_gestion' in vals:
            if self.comentario_gestion:
                raise UserError(_('No pudo guardarse correctamente el comentario: ' + vals['comentario_gestion']))
        if 'gestion_user_id' in vals:
            if self.gestion_user_id:
                raise UserError(_('No pudo guardarse correctamente el usuario del comentario: ' + vals['comentario_gestion']))
        res = super(AccountMoveGestion, self).write(vals)
        return res
