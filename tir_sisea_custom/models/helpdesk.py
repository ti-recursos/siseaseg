# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import datetime
from typing_extensions import assert_type

from dateutil import relativedelta
from odoo import api, fields, models, _
from odoo.addons.helpdesk.models.helpdesk_ticket import TICKET_PRIORITY
from odoo.addons.http_routing.models.ir_http import slug
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from ast import literal_eval

import phonenumbers

import logging
_logger = logging.getLogger(__name__)


"""
Estos son los ticket asociados al cliente
"""
class HelpdeskTicketLines(models.Model):
    _name = "helpdesk.ticket.lines"
    _description = "Tickets Relacionados"
    _order = "sequence asc"


    model_id = fields.Many2one(
        comodel_name='helpdesk.ticket',
        string='Documento'
    )
    sequence = fields.Integer(string="Secuencia")
    parent_id = fields.Many2one('helpdesk.ticket', string='Ticket', ondelete='cascade', required=True)
    subscription_id = fields.Many2one('sale.subscription', string="Suscripción")
    name = fields.Char(string='Asunto', required=True, related='parent_id.name')
    description = fields.Text(string='Descripción', required=True, related='parent_id.description')

    
    
class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"
    _description = 'Helpdesk Ticket'

    count_invoice = fields.Integer(compute="_count_invoices", string='Total Unpaid Documents')

    subscription_id = fields.Many2one('sale.subscription', domain=[('stage_category', '!=', 'closed')],  string="Sale Subscription")
    comment = fields.Text(string='Nota de Cierre de Tiquete')


    reporte_id = fields.Many2one('sale.subscription.soporte', string="Contacto que Reporta")

    persona_reporte = fields.Char(string='Nombre', tracking=True)
    tel_reporte = fields.Char(string='Teléfono', tracking=True)
    movil_reporte = fields.Char(string='Móvil', tracking=True)
    relacion_reporte = fields.Text(string='Relación', tracking=True)
    correo_reporte = fields.Char(string='Correo electrónico', tracking=True)
    
    ticket_ids = fields.One2many(
        'helpdesk.ticket.lines',
        'model_id',
        string='Helpdesk Ticket'
    )
    def action_clean(self):
        self.reporte_id = False
        self.persona_reporte = False
        self.tel_reporte = False
        self.relacion_reporte = False
        self.correo_reporte = False

    @api.onchange('reporte_id')
    def _onchange_reporte_id(self):
        if self.reporte_id:
            self.persona_reporte = self.reporte_id.partner_id.name
            self.tel_reporte = self.reporte_id.partner_id.phone
            self.movil_reporte = self.reporte_id.partner_id.mobile
            self.relacion_reporte = self.reporte_id.partner_id.function
            self.correo_reporte = self.reporte_id.partner_id.email


    '''
        Dirección para tickets
    '''

    partner_direction = fields.Text(string="Dirección", compute='_compute_direction')


    '''
        Notas Temporales de Suscripción
    '''

    n_temp = fields.Char(string='Notas Temporales', tracking=True, compute='_compute_n_temp_subs')

    def _compute_n_temp_subs(self):
        for ticket in self:
            if len(ticket.subscription_id) > 0:
                ticket.n_temp = ticket.subscription_id.n_temp
            else:
                ticket.n_temp = ""
    '''
        Conteo de Tickets
    '''

    ticket_count = fields.Integer("Tickets", compute='_compute_ticket_count')

    def _compute_ticket_count(self):
        # group tickets by partner, and account for each partner in self
        for ticket in self:
            stages_ids = self.env['helpdesk.stage'].search([('is_close', '=', False)]).ids

            tickets = self.env['helpdesk.ticket'].sudo().search([('id', '!=', self.id), ('partner_id', '=', ticket.partner_id.id), ('subscription_id', '=', ticket.subscription_id.id),('stage_id', 'in' , stages_ids)])
            total = len(tickets)
            if total:
                ticket.ticket_count = total
            else:
                ticket.ticket_count = 0
            #self.ticket_count = total

    def action_open_helpdesk_ticket(self):
        stages_ids = self.env['helpdesk.stage'].search([('is_close', '=', False)]).ids

        action = self.env["ir.actions.actions"]._for_xml_id("helpdesk.helpdesk_ticket_action_main_tree")
        action['context'] = {}
        action['domain'] = [('id', '!=', self.id), ('partner_id', '=', self.partner_id.id), ('subscription_id', '=', self.subscription_id.id), ('stage_id', 'in' , stages_ids)]
        return action


    def _compute_direction(self):
        for ticket in self:
            if len(ticket.subscription_id) > 0:
                ticket.partner_direction = ticket.subscription_id.partner_direction
            else:
                ticket.partner_direction = ""

    def write(self, vals):
        if 'stage_id' in vals:
            etapa = self.env['helpdesk.stage'].search([('id', '=', vals['stage_id'])], limit=1)
            if etapa.is_close:
                if not self.comment:
                    _logger.warning(_("Ocurrió un error al finalizar el ticket, valor del campo: "+ str(self.comment)))
                    raise UserError(_('Ocurrió un error al finalizar el ticket, por favor complete el campo Nota de Cierre de Tiquete'))
        if 'team_id' in vals:
            facturas = self.count_invoice
            tolerancia = self.company_id.tolerancia_documentos
            if facturas > tolerancia:
                if not self.user_has_groups('tir_sisea_custom.group_ticket_account'):
                    if not self.env.ref('tir_sisea_custom.team_accounting').id == vals['team_id']:
                        raise UserError(_('Este ticket debe ser asignado a contabilidad'))
        res = super(HelpdeskTicket, self).write(vals)
        return res

    def _count_invoices(self):
        for ticket in self:
            if len(ticket.partner_id) > 0:
                if self.subscription_id:
                    facturas = self.env['account.move'].sudo().search(
                        [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'),('state', 'in', ['posted', 'draft']),
                        ('partner_id', '=', ticket.partner_id.id),
                        ('invoice_origin', '=', self.subscription_id.code)])
                else:
                    facturas = self.env['account.move'].sudo().search(
                        [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'), ('state', 'in', ['posted', 'draft']),
                        ('partner_id', '=', ticket.partner_id.id)])
                total = len(facturas)
                ticket.count_invoice = total
            else:
                ticket.count_invoice = 0

    @api.onchange('subscription_id')
    def onchange_subscription_id(self):
        for ticket in self:
            domain = []
            if len(ticket.subscription_id) > 0:
                domain.append(('subscription_id', '=', ticket.subscription_id.id))
                ticket.partner_id = ticket.subscription_id.partner_id.id
                ticket.partner_direction = ticket.subscription_id.partner_direction
                ticket.action_clean()
                facturas = self.env['account.move'].sudo().search(
                        [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'),('state', 'in', ['posted', 'draft']),
                        ('partner_id', '=', ticket.partner_id.id),
                        ('invoice_origin', '=', self.subscription_id.code)])
                total = len(facturas)
                ticket.count_invoice = total

                tolerancia = ticket.company_id.tolerancia_documentos
                if len(facturas) > tolerancia:
                    ticket.team_id = self.env.ref('tir_sisea_custom.team_accounting')
            """
                TICKETS
            """
            stages_ids = self.env['helpdesk.stage'].search([('is_close', '=', False)]).ids
            domain.append(('partner_id', '=', ticket.partner_id.id))
            domain.append(('partner_id', '<>', False))
            domain.append(('stage_id', 'in' , stages_ids))
            delete_lines = []
            for line in ticket.ticket_ids:
                id_line = line.id
                delete_lines.append(
                    (2, id_line, 0)
                )
            ticket.sudo().write({ 'ticket_ids' : delete_lines })

            tickets = self.env['helpdesk.ticket'].sudo().search(domain)
            if tickets:
                new = []
                for line in tickets:
                    if line.subscription_id:
                        if line.subscription_id.code.isnumeric():
                            sequence = line.subscription_id.code
                        else:
                            sequence = 0
                    else:
                        sequence = 0
                    new.append(
                        (0, 0, {
                            'sequence': sequence,
                            'subscription_id': line.subscription_id or False,
                            'parent_id': line.id
                        })
                    )
                ticket.sudo().write({
                    'ticket_ids': new
                })

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        for ticket in self:
            domain = []
            if len(ticket.partner_id) > 0:
                if ticket.subscription_id == '' or ticket.subscription_id == False:
                    sub_ids = self.env['sale.subscription'].sudo().search([('partner_id', '=', ticket.partner_id.id)]).ids
                    if len(sub_ids) > 0:
                        ticket.subscription_id = sub_ids[0]
                        ticket.partner_direction = ticket.subscription_id.partner_direction
                    else:
                        self.subscription_id = False

                if ticket.subscription_id:
                    facturas = self.env['account.move'].sudo().search(
                        [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'),('state', 'in', ['posted', 'draft']),
                        ('partner_id', '=', ticket.partner_id.id),
                        ('invoice_origin', '=', ticket.subscription_id.code)])
                    ticket.partner_direction = ticket.subscription_id.partner_direction
                    domain.append(('subscription_id', '=', ticket.subscription_id.id))
                else:
                    facturas = self.env['account.move'].sudo().search(
                        [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'), ('state', 'in', ['posted', 'draft']),
                        ('partner_id', '=', ticket.partner_id.id)])
                    ticket.partner_direction = ""
                total = len(facturas)
                ticket.count_invoice = total

                tolerancia = ticket.company_id.tolerancia_documentos
                if len(facturas) > tolerancia:
                    ticket.team_id = self.env.ref('tir_sisea_custom.team_accounting')

                """
                    TICKETS
                """
                stages_ids = self.env['helpdesk.stage'].search([('is_close', '=', False)]).ids
                domain.append(('partner_id', '=', ticket.partner_id.id))
                domain.append(('partner_id', '<>', False))
                domain.append(('stage_id', 'in' , stages_ids))
                delete_lines = []
                for line in ticket.ticket_ids:
                    id_line = line.id
                    delete_lines.append(
                        (2, id_line, 0)
                    )
                ticket.sudo().write({ 'ticket_ids' : delete_lines })
                
                tickets = self.env['helpdesk.ticket'].sudo().search(domain)
                if tickets:
                    new = []
                    for line in tickets:
                        if line.subscription_id:
                            if line.subscription_id.code.isnumeric():
                                sequence = line.subscription_id.code
                            else:
                                sequence = 0
                        else:
                            sequence = 0
                        new.append(
                            (0, 0, {
                                'sequence': sequence,
                                'subscription_id': line.subscription_id or False,
                                'parent_id': line.id
                            })
                        )
                    ticket.sudo().write({
                        'ticket_ids': new
                    })
            else:
                ticket.count_invoice = 0


    def action_view_partner_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if self.subscription_id:
            action['domain'] = [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'),('state', 'in', ['posted', 'draft']),
                ('partner_id', '=', self.partner_id.id),
                ('invoice_origin', '=', self.subscription_id.code)]
        else:
            action['domain'] = [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'), ('state', 'in', ['posted', 'draft']),
            ('partner_id', '=', self.partner_id.id)]

        action['context'] = {'default_move_type':'out_invoice', 'move_type':'out_invoice', 'journal_type': 'sale'}
        return action

    @api.model
    def create(self, vals):
        res = super(HelpdeskTicket, self).create(vals)
        facturas = res.count_invoice
        tolerancia = res.company_id.tolerancia_documentos
        if facturas > tolerancia:
            # Se debe de notificar que se ha desbloqueado la información
            init_team = res.team_id
            final_team = self.env.ref('tir_sisea_custom.team_accounting')

            permiso = False
            if self.user_has_groups('tir_sisea_custom.group_ticket_account'):
                permiso = True
            if init_team.id != final_team and permiso == True:
                msg_body = _(
                    'El usuario: <a href=# data-oe-model=res.users data-oe-id=%d>%s</a> pasó el ticket de <strong>%s</strong> a <strong>%s</strong> <br/> El cliente tiene %s documentos pendientes') % (self.env.user.id, self.env.user.name, final_team.name, init_team.name, str(facturas))
                res.message_post(body=msg_body, message_type='comment')
            if init_team.id != final_team and permiso == False:
                res.team_id = final_team.id

        return res
