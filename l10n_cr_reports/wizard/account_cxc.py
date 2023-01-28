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
    _name = "account.cxc.report.wizard"
    _description = "CxC Account Report"


    date_end = fields.Date(string='Fecha de Fin', required=True, default=fields.Date.today)

    # Reporte CxC

    def cxc_get_report(self):
        data = {
            'model': self._name,
            'ids': self.ids,
            'form': {
                'date_end': self.date_end,
            },
        }

        # ref `module_name.report_id` as reference.
        return self.env.ref('l10n_cr_reports.account_cxc_report').report_action(self, data=data)


    def print_project_report_xls(self):
        record = self.env['account.move'].search([], limit=1)
        data = {
            'ids': self.ids,
            'model': self._name,
            'record': record.id,
        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'account.cxc.report.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte Antigüedad de saldos',
                     },
            'report_type': 'xlsx'
        }
    def get_selection_label(self, object, field_name, field_value):
        return _(dict(self.env[object].fields_get(allfields=[field_name])[field_name]['selection'])[field_value])

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        wizard_record = request.env['account.cxc.report.wizard'].search([])[-1]
        date_end = wizard_record.date_end
        fin = datetime.strptime(str(date_end), '%Y-%m-%d').strftime("%d/%m/%Y")

        facturas = self.env['account.move'].search(
            [('date', '<=', fin), # ('state', '=', 'posted'),
             ('move_type', 'in', ['out_invoice', 'out_refund']), ('payment_state', '=', 'not_paid')
             ], order="partner_id, name asc")
        now_utc = datetime.now(pytz.timezone('UTC'))
        ahora = datetime.strptime(now_utc.strftime("%Y-%m-%d"), "%Y-%m-%d")

        total_sin_vencer = 0
        total_menos_30 = 0
        total_30_60 = 0
        total_61_90 = 0
        total_90_mas = 0

        docs = []
        sheet = workbook.add_worksheet("Resumen CxC")
        bold = workbook.add_format({'bold': True})
        normal = workbook.add_format({'bold': False})

        sheet.write(0, 0, 'Fecha Final', bold)
        sheet.write(0, 1, fin, normal)

        sheet.write(2, 0, 'Cliente', bold)
        sheet.write(2, 1, 'Número', bold)
        sheet.write(2, 2, 'Fecha', bold)
        sheet.write(2, 3, 'Sin Vencer', bold)
        sheet.write(2, 4, 'Igual o menor a 30', bold)
        sheet.write(2, 5, '30 - 60', bold)
        sheet.write(2, 6, '61 - 90', bold)
        sheet.write(2, 7, '+ 90', bold)

        fila = 3
        for factura in facturas:

            if factura.invoice_date_due:
                vencimiento = datetime.strptime(factura.invoice_date_due.strftime("%Y-%m-%d"), "%Y-%m-%d")
            else:
                if factura.invoice_date:
                    vencimiento = datetime.strptime(factura.invoice_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                else:
                    vencimiento = datetime.strptime(factura.periodo_sub.strftime("%Y-%m-%d"), "%Y-%m-%d")
            diff = ahora - vencimiento
            days, seconds = diff.days, diff.seconds

            if factura.name != '/':
                documento = factura.name
            else:
                documento = "Documento Borrador (*" + str(factura.id) + ")"

            if days <= 0:
                total_sin_vencer += factura.amount_residual_signed

                sheet.write(fila, 0, factura.partner_id.name, normal)
                sheet.write(fila, 1, documento, normal)
                sheet.write(fila, 2, factura.date.strftime("%d/%m/%Y"), normal)
                sheet.write(fila, 3, factura.amount_residual_signed, normal)
                sheet.write(fila, 4, 0, normal)
                sheet.write(fila, 5, 0, normal)
                sheet.write(fila, 6, 0, normal)
                sheet.write(fila, 7, 0, normal)

            elif 0 < days <= 30:
                total_menos_30 += factura.amount_residual_signed

                sheet.write(fila, 0, factura.partner_id.name, normal)
                sheet.write(fila, 1, documento, normal)
                sheet.write(fila, 2, factura.date.strftime("%d/%m/%Y"), normal)
                sheet.write(fila, 3, 0, normal)
                sheet.write(fila, 4, factura.amount_residual_signed, normal)
                sheet.write(fila, 5, 0, normal)
                sheet.write(fila, 6, 0, normal)
                sheet.write(fila, 7, 0, normal)

            elif 30 < days <= 60:
                total_30_60 += factura.amount_residual_signed

                sheet.write(fila, 0, factura.partner_id.name, normal)
                sheet.write(fila, 1, documento, normal)
                sheet.write(fila, 2, factura.date.strftime("%d/%m/%Y"), normal)
                sheet.write(fila, 3, 0, normal)
                sheet.write(fila, 4, 0, normal)
                sheet.write(fila, 5, factura.amount_residual_signed, normal)
                sheet.write(fila, 6, 0, normal)
                sheet.write(fila, 7, 0, normal)

            elif 60 < days <= 90:
                total_61_90 += factura.amount_residual_signed

                sheet.write(fila, 0, factura.partner_id.name, normal)
                sheet.write(fila, 1, documento, normal)
                sheet.write(fila, 2, factura.date.strftime("%d/%m/%Y"), normal)
                sheet.write(fila, 3, 0, normal)
                sheet.write(fila, 4, 0, normal)
                sheet.write(fila, 5, 0, normal)
                sheet.write(fila, 6, factura.amount_residual_signed, normal)
                sheet.write(fila, 7, 0, normal)
            elif days > 90:
                total_90_mas += factura.amount_residual_signed

                sheet.write(fila, 0, factura.partner_id.name, normal)
                sheet.write(fila, 1, documento, normal)
                sheet.write(fila, 2, factura.date.strftime("%d/%m/%Y"), normal)
                sheet.write(fila, 3, 0, normal)
                sheet.write(fila, 4, 0, normal)
                sheet.write(fila, 5, 0, normal)
                sheet.write(fila, 6, 0, normal)
                sheet.write(fila, 7, factura.amount_residual_signed, normal)
            fila += 1
        sheet.write(fila, 3, total_sin_vencer, normal)
        sheet.write(fila, 4, total_menos_30, normal)
        sheet.write(fila, 5, total_30_60, normal)
        sheet.write(fila, 6, total_61_90, normal)
        sheet.write(fila, 7, total_90_mas, normal)
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()