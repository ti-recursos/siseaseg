# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.translate import _
from odoo.exceptions import UserError

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from lxml import etree
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"
    """
    Account move reversal wizard, it cancel an account move by reversing it.
    """
    reference_code_id = fields.Many2one("reference.code", string="Reference Code", required=True, )
    reference_document_id = fields.Many2one("reference.document", string="Reference Document Id", required=True, )

    def _prepare_default_reversal(self, move):
        default_values = super()._prepare_default_reversal(move)

        if move.tipo_documento in ('FE', 'TE') and move.state_tributacion == 'rechazado':
            move_type = 'out_invoice'
            tipo_doc = move.tipo_documento
        elif move.move_type == 'out_refund':
            move_type = 'out_invoice'
            tipo_doc = 'ND'
        elif move.move_type == 'out_invoice':
            move_type = 'out_refund'
            tipo_doc = 'NC'
        elif move.move_type == 'in_invoice':
            move_type = 'in_refund'
            tipo_doc = 'NC'
        else:
            tipo_doc = 'ND'
            move_type = 'in_invoice'

        fe_values = {'invoice_id': move.id,
                       'move_type': move_type,
                       'tipo_documento': tipo_doc,
                       'reference_code_id': self.reference_code_id.id,
                       'reference_document_id': self.reference_document_id.id,
                       'economic_activity_id': move.economic_activity_id.id,
                       'payment_methods_id': move.payment_methods_id.id,
                       'state_tributacion': False}

        return {**default_values, **fe_values}
