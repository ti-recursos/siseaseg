# -*- coding: utf-8 -*-
###################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2019-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###################################################################################

from odoo.http import request
from odoo import models, api, _

from datetime import datetime, timedelta
import pytz


class ReportSaleSummaryReportView(models.AbstractModel):
    """
        Abstract Model specially for report template.
        _name = Use prefix `report.` along with `module_name.report_name`
    """
    # _name = 'report.custom_report_odoo12.sale_summary_report_view'
    # _name = 'report.tir_bnet_custom.account_invoice_report_view'
    _name = 'report.l10n_cr_reports.account_cxc_report_view'
    _description = "L10n_cr Reporte CxC"

    @api.model
    def _get_report_values(self, docids, data=None):
        print('_get_report_values l10n_cr_reports')
        now_utc = datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        dia = now_cr.strftime('%d')  # '%02d' % now_cr.day,
        mes = now_cr.strftime('%m')  # '%02d' % now_cr.month,
        anno = now_cr.strftime('%Y')  # str(now_cr.year)[2:4],

        date_cr = now_cr.strftime(anno + "-" + mes + "-" + dia + "T%H:%M:%S")

        date_end = data['form']['date_end']
        fin = datetime.strptime(str(date_end), '%Y-%m-%d').strftime("%d/%m/%Y")
        facturas = self.env['account.move'].search(
            [('date', '<=', date_end),# ('state', '=', 'posted'),
             ('move_type', 'in', ['out_invoice', 'out_refund']),
             ('payment_state', '=', 'not_paid')], order="partner_id, name asc")

        docs = []
        ahora = datetime.strptime(now_utc.strftime("%Y-%m-%d"), "%Y-%m-%d")

        total_sin_vencer = 0
        total_menos_30 = 0
        total_30_60 = 0
        total_61_90 = 0
        total_90_mas = 0

        for factura in facturas:
            if factura.invoice_date_due:
                vencimiento = datetime.strptime(factura.invoice_date_due.strftime("%Y-%m-%d"), "%Y-%m-%d")
            else:
                vencimiento = datetime.strptime(factura.invoice_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
            diff = ahora - vencimiento
            days, seconds = diff.days, diff.seconds

            if factura.name != '/':
                documento = factura.name
            else:
                documento = "Documento Borrador (*" + str(factura.id) + ")"

            if days <= 0:
                total_sin_vencer += factura.amount_residual_signed

                docs.append({
                    'name': documento,
                    'partner': factura.partner_id.name,
                    'date': factura.date.strftime("%d/%m/%Y"),
                    'company': self.env.user.company_id,
                    'sin_vencer': factura.amount_residual_signed,
                    'menos_30': 0,
                    '30_60': 0,
                    '61_90': 0,
                    '90_mas': 0,
                })
            elif 0 < days <= 30:
                total_menos_30 += factura.amount_residual_signed

                docs.append({
                    'name': documento,
                    'partner': factura.partner_id.name,
                    'date': factura.date.strftime("%d/%m/%Y"),
                    'company': self.env.user.company_id,
                    'sin_vencer': 0,
                    'menos_30': factura.amount_residual_signed,
                    '30_60': 0,
                    '61_90': 0,
                    '90_mas': 0,
                })
            elif 30 < days <= 60:
                total_30_60 += factura.amount_residual_signed

                docs.append({
                    'name': documento,
                    'partner': factura.partner_id.name,
                    'date': factura.date.strftime("%d/%m/%Y"),
                    'company': self.env.user.company_id,
                    'sin_vencer': 0,
                    'menos_30': 0,
                    '30_60': factura.amount_residual_signed,
                    '61_90': 0,
                    '90_mas': 0,
                })
            elif 60 < days <= 90:
                total_61_90 += factura.amount_residual_signed

                docs.append({
                    'name': documento,
                    'partner': factura.partner_id.name,
                    'date': factura.date.strftime("%d/%m/%Y"),
                    'company': self.env.user.company_id,
                    'sin_vencer': 0,
                    'menos_30': 0,
                    '30_60': 0,
                    '61_90': factura.amount_residual_signed,
                    '90_mas': 0,
                })
            elif days > 90:
                total_90_mas += factura.amount_residual_signed

                docs.append({
                    'name': documento,
                    'partner': factura.partner_id.name,
                    'date': factura.date.strftime("%d/%m/%Y"),
                    'company': self.env.user.company_id,
                    'sin_vencer': 0,
                    'menos_30': 0,
                    '30_60': 0,
                    '61_90': 0,
                    '90_mas': factura.amount_residual_signed,
                })


        return {
            'doc_ids': data['ids'],
            'doc_model': data['model'],
            'creacion': date_cr,
            'date_end': fin,

            'total_sin_vencer': total_sin_vencer,
            'total_menos_30': total_menos_30,
            'total_30_60': total_30_60,
            'total_61_90': total_61_90,
            'total_90_mas': total_90_mas,


            'total_company': self.env.user.company_id,
            'docs': docs,
        }

