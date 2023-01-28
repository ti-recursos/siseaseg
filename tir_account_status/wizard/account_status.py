# -*- coding: utf-8 -*-

from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
import json
from datetime import datetime, timedelta
import pytz
import io
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import date_utils
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

class SaleSummaryReportWizard(models.TransientModel):
    _name = 'account.status.report.wizard'

    draft_docs = fields.Boolean(string="Documentos Borrador", default=False)

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        domain=[('active', '=', True)],
        help="Partner from which the report will be generated")
    date_start = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    date_end = fields.Date(string='End Date', required=True, default=fields.Date.today)

    # Reporte CxC

    def cxc_get_report(self):
        data = {
            'model': self._name,
            'ids': self.ids,
            'form': {
                'partner_id': self.partner_id.id,
                'date_start': self.date_start,
                'draft_docs': self.draft_docs,
                'date_end': self.date_end,
            },
        }

        # ref `module_name.report_id` as reference.
        return self.env.ref('tir_account_status.account_status_report').report_action(self, data=data)


    def print_project_report_xls(self):
        record = self.env['account.move'].search([], limit=1)
        data = {
            'ids': self.ids,
            'model': self._name,
            'record': record.id,
        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'account.status.report.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Partner Account Balance',
                     },
            'report_type': 'xlsx'
        }
    def get_selection_label(self, object, field_name, field_value):
        return _(dict(self.env[object].fields_get(allfields=[field_name])[field_name]['selection'])[field_value])

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        wizard_record = request.env['account.status.report.wizard'].search([])[-1]
        date_start = wizard_record.date_start
        date_end = wizard_record.date_end
        partner_id = wizard_record.partner_id.id
        draft_docs = wizard_record.draft_docs

        partner = self.env['res.partner'].search([('id', '=', partner_id)], limit=1)

        por_cobrar = partner.property_account_receivable_id.id
        por_pagar = partner.property_account_payable_id.id

        if draft_docs:
            dominio = [('date', '<=', date_end),
            ('parent_state', 'in', ['posted', 'draft']),
            ('partner_id', '=', partner_id),
            ('date', '>=', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)
            ]
        else:
            dominio = [('date', '<=', date_end), 
            ('parent_state', '=', 'posted'),
            ('partner_id', '=', partner_id),
            ('date', '>=', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)]
        
        lineas = self.env['account.move.line'].search(
            dominio, order="date asc, account_id")


        total_debito = 0
        total_credito = 0
        balance = 0
        balance_inicial = 0

        sheet = workbook.add_worksheet("REPORTE")
        header = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#445EC7'})
        bold = workbook.add_format({'bold': True})
        bold_italic = workbook.add_format({'bold': True, 'italic': True})
        normal = workbook.add_format({'bold': False})

        fila = 0

        sheet.write(fila, 0, 'REPORTE ESTADO DE CUENTA', header)


        fecha = workbook.add_format({'num_format': 'dd/mm/yyyy', 'bold': False})
        fecha_bold = workbook.add_format({'num_format': 'dd/mm/yyyy', 'bold': True})

        sheet.write(fila, 4, 'De', header)
        sheet.write(fila, 5, date_start, fecha_bold)
        fila += 1
        sheet.write(fila, 4, 'hasta', header)
        sheet.write(fila, 5, date_end, fecha_bold)

        fila += 2
        sheet.write(fila, 0, 'Socio de Negocio', header)
        sheet.write(fila, 1, partner.name, bold_italic)

        fila += 2

        sheet.write(fila, 0, 'Fecha', header)
        sheet.write(fila, 1, 'Número de Documento', header)
        sheet.write(fila, 2, 'Ref', header)
        sheet.write(fila, 3, 'Debido', header)
        sheet.write(fila, 4, 'Crédito', header)
        sheet.write(fila, 5, 'Balance', header)

        if draft_docs:
            dominio_balance = [
            ('parent_state', 'in', ['posted', 'draft']),
            ('partner_id', '=', partner_id),
            ('date', '<', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)]
            
        else:
            dominio_balance = [
            ('parent_state', '=', 'posted'),
            ('partner_id', '=', partner_id),
            ('date', '<', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)]

        lineas_balance = self.env['account.move.line'].sudo().search(dominio_balance, order="date asc")
        for registro in lineas_balance:
            balance += registro.balance
            balance_inicial += registro.balance

        fila += 1

        sheet.write(fila, 0, '', bold_italic)
        sheet.write(fila, 1, 'Balance Inicial', bold_italic)
        sheet.write(fila, 2, '', bold_italic)
        sheet.write(fila, 3, '', bold_italic)
        sheet.write(fila, 4, '', bold_italic)
        sheet.write(fila, 5, balance_inicial, bold_italic)

        fila += 1

        for linea in lineas:
            total_debito += linea.debit
            total_credito += linea.credit

            balance += linea.balance

            if linea.parent_state == 'draft':
                nombre = str(linea.move_id.id)
            else:
                nombre = linea.move_name

            sheet.write(fila, 0, linea.date, fecha)
            sheet.write(fila, 1, nombre, normal)
            sheet.write(fila, 2, linea.ref or '', normal)
            sheet.write(fila, 3, linea.debit, normal)
            sheet.write(fila, 4, linea.credit, normal)
            sheet.write(fila, 5, balance, normal)
            fila += 1

        
        sheet.write(fila, 0, '', bold_italic)
        sheet.write(fila, 1, 'Balance Final', bold_italic)
        sheet.write(fila, 2, '', bold_italic)
        sheet.write(fila, 3, total_debito, bold_italic)
        sheet.write(fila, 4, total_credito, bold_italic)
        sheet.write(fila, 5, balance, bold_italic)


        '''
            Documentos por cobrar
        '''
        now_utc = datetime.now(pytz.timezone('UTC'))
        ahora = datetime.strptime(now_utc.strftime("%Y-%m-%d"), "%Y-%m-%d")

        if draft_docs:
            dominio_cxc = [
            ('partner_id', '=', partner_id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'in', ['posted', 'draft']),
            ('payment_state', 'in', ['not_paid', 'in_payment'])]
            
        else:
            dominio_cxc = [
            ('partner_id', '=', partner_id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'in_payment'])]

        cxc_docs = self.env['account.move'].search(dominio_cxc, order="date asc")

        sin_vencer = 0
        grupo1_30 = 0
        grupo31_60 = 0
        grupo61_90 = 0
        grupo_m_91 = 0
        total_cxc = 0

        for linea in cxc_docs:
            if linea.invoice_date_due:
                vencimiento = datetime.strptime(linea.invoice_date_due.strftime("%Y-%m-%d"), "%Y-%m-%d")
            else:
                if linea.invoice_date:
                    vencimiento = datetime.strptime(linea.invoice_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                else:
                    vencimiento = datetime.strptime(linea.date.strftime("%Y-%m-%d"), "%Y-%m-%d")

            diff = ahora - vencimiento
            days, seconds = diff.days, diff.seconds
            total_cxc += linea.amount_residual_signed

            if days <= 0:
                sin_vencer += linea.amount_residual_signed
            elif 0 < days <= 30:
                grupo1_30 += linea.amount_residual_signed
            elif 30 < days <= 60:
                grupo31_60 += linea.amount_residual_signed
            elif 60 < days <= 90:
                grupo61_90 += linea.amount_residual_signed
            elif days > 90:
                grupo_m_91 += linea.amount_residual_signed

        fila += 2

        sheet.write(fila, 0, 'Por Cobrar', header)
        fila += 2

        sheet.write(fila, 0, 'Sin Vencer', header)
        sheet.write(fila, 1, '1 - 30', header)
        sheet.write(fila, 2, '31 - 60', header)
        sheet.write(fila, 3, '61 - 90', header)
        sheet.write(fila, 4, '+ 91', header)
        sheet.write(fila, 5, 'Total', header)
        fila += 1

        sheet.write(fila, 0, sin_vencer, normal)
        sheet.write(fila, 1, grupo1_30, normal)
        sheet.write(fila, 2, grupo31_60, normal)
        sheet.write(fila, 3, grupo61_90, normal)
        sheet.write(fila, 4, grupo_m_91, normal)
        sheet.write(fila, 5, total_cxc, normal)



        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()