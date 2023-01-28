# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class Stage(models.Model):
    _inherit = "crm.stage"

    calificado = fields.Boolean('Permiso para Calificado')
    propuesta = fields.Boolean('Permiso para Propuesta')

    formalizacion = fields.Boolean('Permiso para Formalización')
    valida_doc = fields.Boolean('Permiso para Validación de Documentos')

    cuenta_monitoreo = fields.Boolean('Permiso para Cuenta Monitoreo')

    coordinacion = fields.Boolean('Permiso para Coordinación')
    instalacion = fields.Boolean('Permiso para Instalación')
    valida_cuenta = fields.Boolean('Permiso para Validar Cuentas')
    soporte = fields.Boolean('Permiso para Soporte')
    conta = fields.Boolean('Permiso para Contabilidad')
    finalizado = fields.Boolean('Permiso para Finalizado')


class Lead(models.Model):
    _inherit = "crm.lead"

    com_calificado = fields.Text(string="Calificado", required=False)
    com_propuesta = fields.Text(string="Propuesta", required=False)

    com_formalizacion = fields.Text(string="Formalizacion", required=False)
    com_valida_doc = fields.Text(string="Validación de Documentos", required=False)

    com_cuenta_monitoreo = fields.Text(string="Cuenta Monitoreo", required=False)

    com_coordinacion = fields.Text(string="Coordinacion", required=False)
    com_instalacion = fields.Text(string="Instalación", required=False)
    com_valida_cuenta = fields.Text(string="Validación de Cuenta", required=False)
    com_soporte = fields.Text(string="Soporte", required=False)
    com_conta = fields.Text(string="Contabilidad", required=False)
    com_finalizado = fields.Text(string="Finalización", required=False)

    contract = fields.Text(string="Contract")


    def action_view_sale_quotation(self):
        action = super(Lead, self).action_view_sale_quotation()
        contexto = action['context']
        contexto['contract_id'] = self.contract
        action['context'] = contexto
        return action

    def action_new_quotation(self):
        action = super(Lead, self).action_new_quotation()
        contexto = action['context']
        contexto['contract_id'] = self.contract
        action['context'] = contexto
        return action

    def _compute_has_aprove_crm_group(self):
        for record in self:
            record.has_aprove_crm_group = self.user_has_groups('tir_sisea_custom.aprove_crm_group')

    def _default_permiso(self):
        return self.user_has_groups('tir_sisea_custom.aprove_crm_group')

    has_aprove_crm_group = fields.Boolean(string='Permisos para aprobar', compute='_compute_has_aprove_crm_group', default=_default_permiso)

    def write(self, variables):
        if 'stage_id' in variables:
            stage_id = self.env['crm.stage'].browse(variables['stage_id'])

            if stage_id.calificado:
                if not self.user_has_groups('tir_sisea_custom.crm_group_calificado'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')


            if stage_id.propuesta:
                if not self.user_has_groups('tir_sisea_custom.crm_group_propuesta'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_calificado:
                    raise UserError('Por favor completar el comentario de la etapa "Calificado".')

            if stage_id.formalizacion:
                if not self.user_has_groups('tir_sisea_custom.crm_group_formalizacion'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_propuesta:
                    raise UserError('Por favor completar el comentario de la etapa "Propuesta".')

            if stage_id.valida_doc:
                if not self.user_has_groups('tir_sisea_custom.crm_group_valida_doc'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_formalizacion:
                    raise UserError('Por favor completar el comentario de la etapa "Formalización".')

            if stage_id.cuenta_monitoreo:
                if not self.user_has_groups('tir_sisea_custom.crm_group_cuenta_monitoreo'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_valida_doc:
                    raise UserError('Por favor completar el comentario de la etapa "Validación de Documentos".')

            if stage_id.coordinacion:
                if not self.user_has_groups('tir_sisea_custom.crm_group_coordinacion'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_cuenta_monitoreo:
                    raise UserError('Por favor completar el comentario de la etapa "Cuenta de Monitoreo".')

            if stage_id.instalacion:
                if not self.user_has_groups('tir_sisea_custom.crm_group_instalacion'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_coordinacion:
                    raise UserError('Por favor completar el comentario de la etapa "Coordinación".')

            if stage_id.valida_cuenta:
                if not self.user_has_groups('tir_sisea_custom.crm_group_valida_cuentas'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_instalacion:
                    raise UserError('Por favor completar el comentario de la etapa "Instalación".')

            if stage_id.soporte:
                if not self.user_has_groups('tir_sisea_custom.crm_group_soporte'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_valida_cuenta:
                    raise UserError('Por favor completar el comentario de la etapa "Validación de Cuentas".')

            if stage_id.conta:
                if not self.user_has_groups('tir_sisea_custom.crm_group_conta'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_soporte:
                    raise UserError('Por favor completar el comentario de la etapa "Soporte".')
            if stage_id.finalizado:
                if not self.user_has_groups('tir_sisea_custom.crm_group_finalizado'):
                    raise UserError('No cuentas con permiso para mover una oportunidad a esta etapa.')
                if not self.com_conta:
                    raise UserError('Por favor completar el comentario de la etapa "Contabilidad".')

        if 'com_cuenta_monitoreo' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Cuenta Monitoreo:<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_cuenta_monitoreo'])
            self.message_post(body=msg_body)
        if 'com_calificado' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Calificado:<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_calificado'])
            self.message_post(body=msg_body)
        if 'com_propuesta' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Propuesta:<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_propuesta'])
            self.message_post(body=msg_body)
        if 'com_formalizacion' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Formalización.<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_formalizacion'])
            self.message_post(body=msg_body)
        if 'com_valida_doc' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Valida Documentos.<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_valida_doc'])
            self.message_post(body=msg_body)
        if 'com_coordinacion' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Coordinación. <br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_coordinacion'])
            self.message_post(body=msg_body)
        if 'com_instalacion' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Instalación.<br/><br/> %s. ') % (str(self.stage_id.name).upper(), variables['com_instalacion'])
            self.message_post(body=msg_body)
        if 'com_valida_cuenta' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s.<br/><br/>Comentario de etapa Validación de Cuenta. <br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_valida_cuenta'])
            self.message_post(body=msg_body)
        if 'com_soporte' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s. <br/><br/>Comentario de etapa Soporte.<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_soporte'])
            self.message_post(body=msg_body)
        if 'com_conta' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s<br/><br/>Comentario de etapa Contabilidad.<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_conta'])
            self.message_post(body=msg_body)
        if 'com_finalizado' in variables:
            msg_body = _(
                '[ETAPA ACTUAL] %s.<br/><br/>Comentario de etapa Finalizado.<br/><br/>%s. ') % (str(self.stage_id.name).upper(), variables['com_finalizado'])
            self.message_post(body=msg_body)


        return super(Lead, self).write(variables)

    def action_return_stage(self):
        for record in self:
            sequencia = int(record.stage_id.sequence)
            primera = self.env.ref('crm.stage_lead1')
            if record.stage_id.id != primera.id:
                stage = self.env['crm.stage'].search([('sequence', '=', (sequencia - 1))], limit=1)
                if len(stage) > 0:
                    record.stage_id = stage.id

    def action_next_stage(self):
        for record in self:
            sequencia = int(record.stage_id.sequence)

            stage = self.env['crm.stage'].search([('sequence', '=', (sequencia + 1))], limit=1)
            ultima = self.env.ref('tir_sisea_custom.stage_lead11')
            if record.stage_id.id != ultima.id:
                record.stage_id = stage.id

