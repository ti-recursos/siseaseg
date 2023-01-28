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

import datetime
import pytz

class ProjectReportParser(models.AbstractModel):
    _name = 'report.l10n_cr_reports.project_report_template'
    _description = "L10n_cr Project"

    def get_selection_label(self, object, field_name, field_value):
        return _(dict(self.env[object].fields_get(allfields=[field_name])[field_name]['selection'])[field_value])

    def _get_report_values(self, docids, data=None):
        now_utc = datetime.datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        dia = now_cr.strftime('%d')  # '%02d' % now_cr.day,
        mes = now_cr.strftime('%m')  # '%02d' % now_cr.month,
        anno = now_cr.strftime('%Y')  # str(now_cr.year)[2:4],

        date_cr = now_cr.strftime(anno + "-" + mes + "-" + dia + "T%H:%M:%S")

        wizard_record = request.env['account.move.reports.custom'].search([])[-1]

        domain = []
        docs = []

        if wizard_record.doc_clientes:
            domain.insert(len(domain), 'out_invoice')
            domain.insert(len(domain), 'out_refund')
        if wizard_record.doc_proveedores:
            domain.insert(len(domain), 'in_invoice')
            domain.insert(len(domain), 'in_refund')
        date_start = wizard_record.date_start
        date_end = wizard_record.date_end

        inicio = datetime.datetime.strptime(str(date_start), '%Y-%m-%d').strftime("%d/%m/%Y")
        fin = datetime.datetime.strptime(str(date_end), '%Y-%m-%d').strftime("%d/%m/%Y")

        facturas = self.env['account.move'].search(
            [('date', '>=', date_start), ('date', '<=', date_end), ('state', '=', 'posted'),
             ('move_type', 'in', domain)])

        # Totales
        total_amount_untaxed_total = 0
        total_amount_total = 0
        total_descuento = 0

        # Totales Impuestos
        total_tax_cruz_roja = 0
        total_tax_911 = 0
        total_tax_iva = 0

        total_iva_0 = 0
        total_iva_0_nd = 0
        total_iva_1_tr = 0
        total_iva_1_nd = 0
        total_iva_2_tr = 0
        total_iva_2_nd = 0

        total_iva_4_tr = 0
        total_iva_4_nd = 0

        total_iva_4_tran = 0
        total_iva_4_tran_nd = 0

        total_iva_8_tran = 0
        total_iva_8_tran_nd = 0
        total_iva_13 = 0
        total_iva_13_nd = 0
        total_imp_serv = 0
        total_otros = 0
        total_otros_nd = 0
        total_exento = 0

        for factura in facturas:
            tax_lines = factura.line_ids.filtered(lambda line: line.tax_line_id)
            tax_balance_multiplicator = -1 if factura.is_inbound(True) else 1

            # Impuestos
            iva_0 = 0
            iva_0_nd = 0
            iva_1_tr = 0
            iva_1_nd = 0
            iva_2_tr = 0
            iva_2_nd = 0

            iva_4_tr = 0
            iva_4_nd = 0

            iva_4_tran = 0
            iva_4_tran_nd = 0

            iva_8_tran = 0
            iva_8_tran_nd = 0
            iva_13 = 0
            iva_13_nd = 0

            imp_serv = 0
            otros = 0
            otros_nd = 0
            exento = 0
            line_tax = 0
            doc_total = 0

            tax_cruz_roja = 0
            tax_911 = 0
            tax_iva = 0
            descuento = 0

            for line in tax_lines:

                # Control IVA 0
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '01' and not line.tax_line_id.non_tax_deductible:
                    iva_0 += tax_balance_multiplicator * (line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '01' and line.tax_line_id.non_tax_deductible:
                    iva_0_nd += tax_balance_multiplicator * (line.balance)

                # Control IVA 1
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '02' and not line.tax_line_id.non_tax_deductible:
                    iva_1_tr += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '02' and line.tax_line_id.non_tax_deductible:
                    iva_1_nd += tax_balance_multiplicator * (
                        line.balance)

                # Control IVA 2
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '03' and not line.tax_line_id.non_tax_deductible:
                    iva_2_tr += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '03' and line.tax_line_id.non_tax_deductible:
                    iva_2_nd += tax_balance_multiplicator * (
                        line.balance)

                # Control IVA 4
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '04' and not line.tax_line_id.non_tax_deductible:
                    iva_4_tr += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '04' and line.tax_line_id.non_tax_deductible:
                    iva_4_nd += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '06' and not line.tax_line_id.non_tax_deductible:
                    iva_4_tran += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '06' and line.tax_line_id.non_tax_deductible:
                    iva_4_tran_nd += tax_balance_multiplicator * (
                        line.balance)

                # Control IVA 8
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '07' and not line.tax_line_id.non_tax_deductible:
                    iva_8_tran += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '07' and line.tax_line_id.non_tax_deductible:
                    iva_8_tran_nd += tax_balance_multiplicator * (
                        line.balance)

                # Control IVA 13
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '08' and not line.tax_line_id.non_tax_deductible:
                    iva_13 += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '01' and line.tax_line_id.iva_tax_code == '08' and line.tax_line_id.non_tax_deductible:
                    iva_13_nd += tax_balance_multiplicator * (
                        line.balance)

                # Control Otros
                if line.tax_line_id.tax_code == '99' and not line.tax_line_id.non_tax_deductible:
                    otros += tax_balance_multiplicator * (
                        line.balance)
                if line.tax_line_id.tax_code == '99' and line.tax_line_id.non_tax_deductible:
                    otros_nd += tax_balance_multiplicator * (
                        line.balance)

                # Control Impuesto de Servicio
                if line.tax_line_id.tax_code == 'service' and line.tax_line_id.iva_tax_code == '06':
                    imp_serv += tax_balance_multiplicator * (
                        line.balance)

                # Control de Exentos
                if line.tax_line_id.tax_code == '00':
                    exento += tax_balance_multiplicator * (
                        line.balance)

                if line.tax_line_id.tax_code == 'otroscargos':
                    if line.tax_line_id.iva_tax_desc == 'Cargo Cruz Roja':
                        tax_cruz_roja += tax_balance_multiplicator * (
                            line.balance)
                    elif line.tax_line_id.iva_tax_desc == 'Cargo 911':
                        tax_911 += tax_balance_multiplicator * (
                            line.balance)
                else:
                    tax_iva += tax_balance_multiplicator * (line.balance)

            for line in factura.line_ids:
                descuento += ((line.price_unit * line.quantity) - line.price_subtotal)

            # Acumulador de Totales
            if factura.move_type == 'out_refund':
                total_tax_cruz_roja = total_tax_cruz_roja - tax_cruz_roja
                total_tax_911 = total_tax_911 - tax_911
                total_tax_iva = total_tax_iva - tax_iva

                total_iva_0 = total_iva_0 - iva_0
                total_iva_0_nd = total_iva_0_nd - iva_0_nd
                total_iva_1_tr = total_iva_1_tr - iva_1_tr
                total_iva_1_nd = total_iva_1_nd - iva_1_nd
                total_iva_2_tr = total_iva_2_tr - total_iva_2_tr
                total_iva_2_nd = total_iva_2_nd - iva_2_nd

                total_iva_4_tr = total_iva_4_tr - iva_4_tr
                total_iva_4_nd = total_iva_4_nd - iva_4_nd

                total_iva_4_tran = total_iva_4_tran - iva_4_tran
                total_iva_4_tran_nd = total_iva_4_tran_nd - iva_4_tran_nd

                total_iva_8_tran = total_iva_8_tran - iva_8_tran
                total_iva_8_tran_nd = total_iva_8_tran_nd - iva_8_tran_nd
                total_iva_13 = total_iva_13 - iva_13
                total_iva_13_nd = total_iva_13_nd - iva_13_nd
                total_imp_serv = total_imp_serv - imp_serv
                total_otros = total_otros - otros
                total_otros_nd = total_otros_nd - otros_nd
                total_exento = total_exento - exento

                total_amount_untaxed_total = total_amount_untaxed_total + factura.amount_untaxed_signed
                total_descuento = total_descuento - descuento
                total_amount_total = total_amount_total - factura.amount_total_signed
                datos = {'origen': 'Cliente', 'company': self.env.user.company_id, 'tipo': factura.name,
                         'date': factura.date.strftime("%d/%m/%Y"), 'partner_id': factura.partner_id.name,
                         'economic_activity_id': factura.economic_activity_id.code or '', 'invoice_name': factura.name,
                         'doc_referencia': factura.invoice_id.name or '', 'neto': factura.amount_untaxed_signed,
                         'iva_0': -1 * iva_0, 'iva_0_nd': -1 * iva_0_nd, 'iva_1_tr': -1 * iva_1_tr,
                         'iva_1_nd': -1 * iva_1_nd, 'iva_4_tran': -1 * iva_4_tran, 'iva_4_tran_nd': -1 * iva_4_tran_nd,
                         'iva_8_tran': -1 * iva_8_tran, 'iva_8_tran_nd': -1 * iva_8_tran_nd, 'iva_13': -1 * iva_13,
                         'iva_13_nd': -1 * iva_13_nd, 'otros': -1 * otros, 'otros_nd': -1 * otros_nd,
                         'imp_serv': -1 * imp_serv, 'exento': -1 * exento,
                         'amount_tax_signed': factura.amount_tax_signed, 'descuento': -1 * descuento,
                         'amount_total_signed': factura.amount_total_signed}

                if factura.tipo_documento:
                    datos['tipo_documento'] = self.get_selection_label('account.move', 'tipo_documento',factura.tipo_documento)
                else:
                    datos['tipo_documento'] = ''

                if factura.state_tributacion:
                    datos['state_tributacion'] = self.get_selection_label('account.move', 'state_tributacion',factura.state_tributacion)
                else:
                    datos['state_tributacion'] = ''

                datos['state'] = self.get_selection_label('account.move', 'state', factura.state)
                datos['payment_state'] = self.get_selection_label('account.move', 'payment_state', factura.payment_state)

                docs.insert(len(docs), datos)


            elif factura.move_type == 'out_invoice':
                total_tax_cruz_roja = total_tax_cruz_roja + tax_cruz_roja
                total_tax_911 = total_tax_911 + tax_911
                total_tax_iva = total_tax_iva + tax_iva

                total_iva_0 = total_iva_0 + iva_0
                total_iva_0_nd = total_iva_0_nd + iva_0_nd
                total_iva_1_tr = total_iva_1_tr + iva_1_tr
                total_iva_1_nd = total_iva_1_nd + iva_1_nd
                total_iva_2_tr = total_iva_2_tr + total_iva_2_tr
                total_iva_2_nd = total_iva_2_nd + iva_2_nd

                total_iva_4_tr = total_iva_4_tr + iva_4_tr
                total_iva_4_nd = total_iva_4_nd + iva_4_nd

                total_iva_4_tran = total_iva_4_tran + iva_4_tran
                total_iva_4_tran_nd = total_iva_4_tran_nd + iva_4_tran_nd

                total_iva_8_tran = total_iva_8_tran + iva_8_tran
                total_iva_8_tran_nd = total_iva_8_tran_nd + iva_8_tran_nd
                total_iva_13 = total_iva_13 + iva_13
                total_iva_13_nd = total_iva_13_nd + iva_13_nd
                total_imp_serv = total_imp_serv + imp_serv
                total_otros = total_otros + otros
                total_otros_nd = total_otros_nd + otros_nd
                total_exento = total_exento + exento

                total_amount_untaxed_total = total_amount_untaxed_total + factura.amount_untaxed_signed
                total_descuento = total_descuento + descuento
                total_amount_total = total_amount_total + factura.amount_total_signed

                datos = {'origen': 'Cliente', 'company': self.env.user.company_id, 'tipo': factura.name,
                         'date': factura.date.strftime("%d/%m/%Y"), 'partner_id': factura.partner_id.name,
                         'economic_activity_id': factura.economic_activity_id.code or '', 'invoice_name': factura.name,
                         'doc_referencia': factura.invoice_id.name or '', 'neto': factura.amount_untaxed_signed,
                         'iva_0': iva_0, 'iva_0_nd': iva_0_nd, 'iva_1_tr': iva_1_tr, 'iva_1_nd': iva_1_nd,
                         'iva_4_tran': iva_4_tran, 'iva_4_tran_nd': iva_4_tran_nd, 'iva_8_tran': iva_8_tran,
                         'iva_8_tran_nd': iva_8_tran_nd, 'iva_13': iva_13, 'iva_13_nd': iva_13_nd, 'otros': otros,
                         'otros_nd': otros_nd, 'imp_serv': imp_serv, 'exento': exento,
                         'amount_tax_signed': factura.amount_tax_signed, 'descuento': descuento,
                         'amount_total_signed': factura.amount_total_signed}

                if factura.tipo_documento:
                    datos['tipo_documento'] = self.get_selection_label('account.move', 'tipo_documento',
                                                                       factura.tipo_documento)
                else:
                    datos['tipo_documento'] = ''

                if factura.state_tributacion:
                    datos['state_tributacion'] = self.get_selection_label('account.move', 'state_tributacion',
                                                                       factura.state_tributacion)
                else:
                    datos['state_tributacion'] = ''

                datos['state'] = self.get_selection_label('account.move', 'state', factura.state)
                datos['payment_state'] = self.get_selection_label('account.move', 'payment_state',
                                                                  factura.payment_state)

                docs.insert(len(docs), datos)

            elif factura.move_type == 'in_refund':
                total_tax_cruz_roja = total_tax_cruz_roja - tax_cruz_roja
                total_tax_911 = total_tax_911 - tax_911
                total_tax_iva = total_tax_iva - tax_iva

                total_iva_0 = total_iva_0 - iva_0
                total_iva_0_nd = total_iva_0_nd - iva_0_nd
                total_iva_1_tr = total_iva_1_tr - iva_1_tr
                total_iva_1_nd = total_iva_1_nd - iva_1_nd
                total_iva_2_tr = total_iva_2_tr - total_iva_2_tr
                total_iva_2_nd = total_iva_2_nd - iva_2_nd

                total_iva_4_tr = total_iva_4_tr - iva_4_tr
                total_iva_4_nd = total_iva_4_nd - iva_4_nd

                total_iva_4_tran = total_iva_4_tran - iva_4_tran
                total_iva_4_tran_nd = total_iva_4_tran_nd - iva_4_tran_nd

                total_iva_8_tran = total_iva_8_tran - iva_8_tran
                total_iva_8_tran_nd = total_iva_8_tran_nd - iva_8_tran_nd
                total_iva_13 = total_iva_13 - iva_13
                total_iva_13_nd = total_iva_13_nd - iva_13_nd
                total_imp_serv = total_imp_serv - imp_serv
                total_otros = total_otros - otros
                total_otros_nd = total_otros_nd - otros_nd
                total_exento = total_exento - exento

                total_amount_untaxed_total = total_amount_untaxed_total + factura.amount_untaxed_signed
                total_descuento = total_descuento - descuento
                total_amount_total = total_amount_total - factura.amount_total_signed

                datos = {'origen': 'Proveedor', 'company': self.env.user.company_id, 'tipo': factura.name,
                         'date': factura.date.strftime("%d/%m/%Y"), 'partner_id': factura.partner_id.name,
                         'economic_activity_id': factura.economic_activity_id.code or '', 'invoice_name': factura.name,
                         'doc_referencia': factura.invoice_id.name or '', 'neto': factura.amount_untaxed_signed,
                         'iva_0': -1 * iva_0, 'iva_0_nd': -1 * iva_0_nd, 'iva_1_tr': -1 * iva_1_tr,
                         'iva_1_nd': -1 * iva_1_nd, 'iva_4_tran': -1 * iva_4_tran, 'iva_4_tran_nd': -1 * iva_4_tran_nd,
                         'iva_8_tran': -1 * iva_8_tran, 'iva_8_tran_nd': -1 * iva_8_tran_nd, 'iva_13': -1 * iva_13,
                         'iva_13_nd': -1 * iva_13_nd, 'otros': -1 * otros, 'otros_nd': -1 * otros_nd,
                         'imp_serv': -1 * imp_serv, 'exento': -1 * exento,
                         'amount_tax_signed': factura.amount_tax_signed, 'descuento': -1 * descuento,
                         'amount_total_signed': factura.amount_total_signed}

                if factura.tipo_documento:
                    datos['tipo_documento'] = self.get_selection_label('account.move', 'tipo_documento',
                                                                       factura.tipo_documento)
                else:
                    datos['tipo_documento'] = ''

                if factura.state_tributacion:
                    datos['state_tributacion'] = self.get_selection_label('account.move', 'state_tributacion',
                                                                       factura.state_tributacion)
                else:
                    datos['state_tributacion'] = ''

                datos['state'] = self.get_selection_label('account.move', 'state', factura.state)
                datos['payment_state'] = self.get_selection_label('account.move', 'payment_state',
                                                                  factura.payment_state)

                docs.insert(len(docs), datos)

            elif factura.move_type == 'in_invoice':
                total_tax_cruz_roja = total_tax_cruz_roja + tax_cruz_roja
                total_tax_911 = total_tax_911 + tax_911
                total_tax_iva = total_tax_iva + tax_iva

                total_iva_0 = total_iva_0 + iva_0
                total_iva_0_nd = total_iva_0_nd + iva_0_nd
                total_iva_1_tr = total_iva_1_tr + iva_1_tr
                total_iva_1_nd = total_iva_1_nd + iva_1_nd
                total_iva_2_tr = total_iva_2_tr + total_iva_2_tr
                total_iva_2_nd = total_iva_2_nd + iva_2_nd

                total_iva_4_tr = total_iva_4_tr + iva_4_tr
                total_iva_4_nd = total_iva_4_nd + iva_4_nd

                total_iva_4_tran = total_iva_4_tran + iva_4_tran
                total_iva_4_tran_nd = total_iva_4_tran_nd + iva_4_tran_nd

                total_iva_8_tran = total_iva_8_tran + iva_8_tran
                total_iva_8_tran_nd = total_iva_8_tran_nd + iva_8_tran_nd
                total_iva_13 = total_iva_13 + iva_13
                total_iva_13_nd = total_iva_13_nd + iva_13_nd
                total_imp_serv = total_imp_serv + imp_serv
                total_otros = total_otros + otros
                total_otros_nd = total_otros_nd + otros_nd
                total_exento = total_exento + exento

                total_amount_untaxed_total = total_amount_untaxed_total + factura.amount_untaxed_signed
                total_descuento = total_descuento + descuento
                total_amount_total = total_amount_total + factura.amount_total_signed

                datos = {'origen': 'Proveedor', 'company': self.env.user.company_id, 'tipo': factura.name,
                         'date': factura.date.strftime("%d/%m/%Y"), 'partner_id': factura.partner_id.name,
                         'economic_activity_id': factura.economic_activity_id.code or '', 'invoice_name': factura.name,
                         'doc_referencia': factura.invoice_id.name or '', 'neto': factura.amount_untaxed_signed,
                         'iva_0': iva_0, 'iva_0_nd': iva_0_nd, 'iva_1_tr': iva_1_tr, 'iva_1_nd': iva_1_nd,
                         'iva_4_tran': iva_4_tran, 'iva_4_tran_nd': iva_4_tran_nd, 'iva_8_tran': iva_8_tran,
                         'iva_8_tran_nd': iva_8_tran_nd, 'iva_13': iva_13, 'iva_13_nd': iva_13_nd, 'otros': otros,
                         'otros_nd': otros_nd, 'imp_serv': imp_serv, 'exento': exento,
                         'amount_tax_signed': factura.amount_tax_signed, 'descuento': descuento,
                         'amount_total_signed': factura.amount_total_signed}

                if factura.tipo_documento:
                    datos['tipo_documento'] = self.get_selection_label('account.move', 'tipo_documento',
                                                                       factura.tipo_documento)
                else:
                    datos['tipo_documento'] = ''

                if factura.state_tributacion:
                    datos['state_tributacion'] = self.get_selection_label('account.move', 'state_tributacion',
                                                                       factura.state_tributacion)
                else:
                    datos['state_tributacion'] = ''

                datos['state'] = self.get_selection_label('account.move', 'state', factura.state)
                datos['payment_state'] = self.get_selection_label('account.move', 'payment_state',
                                                                  factura.payment_state)

                docs.insert(len(docs), datos)


        return {
            'doc_ids': data['ids'],
            'doc_model': data['model'],
            'creacion': date_cr,
            'date_start': inicio,
            'date_end': fin,

            'total_company': self.env.user.company_id,
            'docs': docs,
        }