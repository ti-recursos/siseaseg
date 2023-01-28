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
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
import json
import datetime
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


import logging
_logger = logging.getLogger(__name__)

from xml.sax.saxutils import escape

class ProjectReportButton(models.TransientModel):
    _name = "account.move.reports.custom"
    _description = "Account Move Reports Custom"

    economic_activity_id = fields.Many2one("economic.activity", string="Actividad Económica", required=False)

    doc_clientes = fields.Boolean(string='Clientes')
    doc_proveedores = fields.Boolean(string='Proveedores')

    date_start = fields.Date(string='Fecha de Inicio', required=True, default=fields.Date.today)
    date_end = fields.Date(string='Fecha de Fin', required=True, default=fields.Date.today)

    def print_project_report_pdf(self):

        #active_record = self._context['active_id']
        record = self.env['account.move'].search([], limit=1)

        data = {
            'ids': self.ids,
            'model': self._name,
            'record': record.id,
        }
        return self.env.ref('l10n_cr_reports.report_project_pdf').report_action(self, data=data)

    def print_project_report_xls(self):

        record = self.env['account.move'].search([], limit=1)
        data = {
            'ids': self.ids,
            'model': self._name,
            'record': record.id,
        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'account.move.reports.custom',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Impuestos',
                     },
            'report_type': 'xlsx'
        }

    def get_selection_label(self, object, field_name, field_value):
        if field_value:
            return _(dict(self.env[object].fields_get(allfields=[field_name])[field_name]['selection'])[field_value])
        else:
            return ''

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        wizard_record = request.env['account.move.reports.custom'].search([])[-1]

        domain = []
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
            [('invoice_date', '>=', date_start), ('invoice_date', '<=', date_end), ('state', '=', 'posted'),
             ('move_type', 'in', domain), ('economic_activity_id', '=', wizard_record.economic_activity_id.id)
             ], order='invoice_date asc')

        #report = self.env['base.document.layout'].sudo().search([], limit=1)

        sheet = workbook.add_worksheet("Reporte Facturación")
        format2 = workbook.add_format({'font_size': 12, 'bold': True, 'bg_color': '#714B67', 'font_color': 'white'})
        format3 = workbook.add_format({'font_size': 10})
        format4 = workbook.add_format({'font_size': 10, 'num_format': '₡#,##0.00'})
        format5 = workbook.add_format({'font_size': 12, 'bold': True, 'bg_color': '#00A09D', 'font_color': 'white'})
        format6 = workbook.add_format({'font_size': 10})
        format6.set_num_format(10)
        negrita_numero = workbook.add_format({'font_size': 10, 'bold': True, 'num_format': '₡#,##0.00'})
        negrita_numero_border = workbook.add_format({'font_size': 10, 'bold': True, 'num_format': '₡#,##0.00'})
        negrita_numero_border.set_bottom(6)

        sheet.write(0, 0, 'Fecha Inicio', format2)
        sheet.write(0, 1, inicio, format3)
        sheet.write(0, 2, 'Fecha Final', format2)
        sheet.write(0, 3, fin, format3)

        documentos = []
        total_invoices = len(facturas)
        current_invoice = 0
        compras = []
        linea_compras = []
        if total_invoices == 0:
            workbook.close()
            output.seek(0)
            response.stream.write(output.read())
            output.close()
        else:
            for inv in facturas:
                partner_type = ''
                if inv.partner_id.identification_id.code == '05':
                    partner_type = 'exterior'
                else:
                    partner_type = 'local'

                current_invoice += 1
                currency = inv.currency_id
                # Validate if invoice currency is the same as the company currency
                if currency.name == inv.company_id.currency_id.name:
                    currency_rate = 1
                else:
                    currency_rate = round(1.0 / currency.rate, 5)
                # Generamos las líneas de la factura
                lines = dict()
                impuestos_arr = []
                otros_cargos = dict()
                otros_cargos_id = 0
                line_number = 0
                total_otros_cargos = 0.0
                total_iva_devuelto = 0.0
                total_servicio_salon = 0.0
                total_servicio_gravado = 0.0
                total_servicio_exento = 0.0
                total_servicio_exonerado = 0.0
                total_mercaderia_gravado = 0.0
                total_mercaderia_exento = 0.0
                total_mercaderia_exonerado = 0.0
                total_descuento = 0.0
                total_impuestos = 0.0
                base_subtotal = 0.0
                for inv_line in inv.invoice_line_ids:
                    if inv_line.display_type not in ['line_section', 'line_note'] and inv_line.account_id is not False:
                        # Revisamos si está línea es de Otros Cargos
                        if inv_line.product_id and inv_line.product_id.id == self.env.ref(
                                'l10n_cr_invoice.product_iva_devuelto').id:
                            total_iva_devuelto = -inv_line.price_total

                        else:
                            line_number += 1
                            price = inv_line.price_unit
                            quantity = inv_line.quantity
                            if not quantity:
                                continue

                            line_taxes = inv_line.tax_ids.compute_all(
                                price, currency, 1,
                                product=inv_line.product_id,
                                partner=inv_line.partner_id)

                            price_unit = round(line_taxes['total_excluded'], 5)

                            base_line = round(price_unit * quantity, 5)
                            descuento = inv_line.discount and round(
                                price_unit * quantity * inv_line.discount / 100.0,
                                5) or 0.0

                            subtotal_line = round(base_line - descuento, 5)

                            # Corregir error cuando un producto trae en el nombre "", por ejemplo: "disco duro"
                            # Esto no debería suceder, pero, si sucede, lo corregimos
                            if inv_line.name[:156].find('"'):
                                detalle_linea = inv_line.name[:160].replace(
                                    '"', '')

                            line = {
                                "cantidad": quantity,
                                "detalle": escape(detalle_linea),
                                "precioUnitario": price_unit,
                                "montoTotal": base_line,
                                "subtotal": subtotal_line,
                                "BaseImponible": subtotal_line,
                                "unidadMedida": inv_line.product_uom_id and inv_line.product_uom_id.code or 'Sp'
                            }

                            if inv_line.product_id:
                                line["codigo"] = inv_line.product_id.default_code or ''
                                line["codigoProducto"] = inv_line.product_id.code or ''
                                if inv_line.product_id.cabys_code:
                                    line["codigoCabys"] = inv_line.product_id.cabys_code
                                elif inv_line.product_id.categ_id and inv_line.product_id.categ_id.cabys_code:
                                    line["codigoCabys"] = inv_line.product_id.categ_id.cabys_code

                            if inv.tipo_documento == 'FEE' and inv_line.tariff_head:
                                line["partidaArancelaria"] = inv_line.tariff_head

                            if inv_line.discount and price_unit > 0:
                                total_descuento += descuento
                                line["montoDescuento"] = descuento
                                line["naturalezaDescuento"] = inv_line.discount_note or 'Descuento Comercial'

                            # Se generan los impuestos
                            taxes = dict()
                            _line_tax = 0.0
                            _tax_exoneration = False
                            _percentage_exoneration = 0
                            if inv_line.tax_ids:
                                type_line = ''
                                if not inv_line.product_uom_id or inv_line.product_uom_id.category_id.name == 'Services' or inv_line.product_id.type == 'service':
                                    type_line = 'servicio'
                                else:
                                    type_line = 'mercaderia'

                                
                                tax_index = 0

                                taxes_lookup = {}
                                for i in inv_line.tax_ids:
                                    if i.has_exoneration:
                                        _tax_exoneration = i.has_exoneration
                                        taxes_lookup[i.id] = {'id_tax': i.id,
                                                            'type_line': type_line + ' exonerado',
                                                            'partner_type': partner_type,
                                                            'tax_code': i.tax_root.tax_code,
                                                            'tarifa': i.tax_root.amount,
                                                            'iva_tax_desc': i.tax_root.iva_tax_desc,
                                                            'iva_tax_code': i.tax_root.iva_tax_code,
                                                            'exoneration_percentage': i.percentage_exoneration,
                                                            'include_base_amount': i.include_base_amount,
                                                            'amount_exoneration': i.amount}
                                    else:
                                        taxes_lookup[i.id] = {'id_tax': i.id,
                                                            'type_line': type_line,
                                                            'partner_type': partner_type,
                                                            'tax_code': i.tax_code,
                                                            'tarifa': i.amount,
                                                            'iva_tax_desc': i.iva_tax_desc,
                                                            'include_base_amount': i.include_base_amount,
                                                            'iva_tax_code': i.iva_tax_code}

                                subsiguiente_impuesto = []
                                subtotal_temporal = subtotal_line
                                for i in line_taxes['taxes']:
                                    if taxes_lookup[i['id']]['include_base_amount']:
                                        if taxes_lookup[i['id']]['tax_code'] == '02':
                                            tax_index += 1
                                            # tax_amount = round(i['amount'], 5) * quantity
                                            tax_amount = round(subtotal_line * taxes_lookup[i['id']]['tarifa'] / 100, 5)
                                            base_on = round(subtotal_line, 5)
                                            _line_tax += tax_amount
                                            tax = {
                                                'codigo': taxes_lookup[i['id']]['tax_code'],
                                                'tarifa': taxes_lookup[i['id']]['tarifa'],
                                                'monto': tax_amount,
                                                'base_on': base_on,
                                                'type_line': taxes_lookup[i['id']]['type_line'],
                                                'partner_type': taxes_lookup[i['id']]['partner_type'],
                                                'iva_tax_desc': taxes_lookup[i['id']]['iva_tax_desc'],
                                                'iva_tax_code': taxes_lookup[i['id']]['iva_tax_code'],
                                            }

                                            subtotal_temporal += tax_amount
                                            taxes[tax_index] = tax
                                            line["impuesto"] = taxes

                                        subsiguiente_impuesto.insert(len(subsiguiente_impuesto), i['id'])
                                for i in line_taxes['taxes']:
                                    if i['id'] not in subsiguiente_impuesto:
                                        subtotal_line_temp = 0
                                        if len(subsiguiente_impuesto) > 0:
                                            subtotal_line_temp += subtotal_temporal
                                        else:
                                            subtotal_line_temp += subtotal_line

                                        if taxes_lookup[i['id']]['tax_code'] == 'service':
                                            total_servicio_salon += round(
                                                subtotal_line_temp * taxes_lookup[i['id']]['tarifa'] / 100, 5)

                                        elif taxes_lookup[i['id']]['tax_code'] != '00':
                                            tax_index += 1
                                            # tax_amount = round(i['amount'], 5) * quantity
                                            tax_amount = round(subtotal_line_temp * taxes_lookup[i['id']]['tarifa'] / 100,
                                                                5)
                                            base_on = round(subtotal_line_temp, 5)
                                            _line_tax += tax_amount
                                            tax = {
                                                'id': taxes_lookup[i['id']]['id_tax'],
                                                'codigo': taxes_lookup[i['id']]['tax_code'],
                                                'tarifa': taxes_lookup[i['id']]['tarifa'],
                                                'monto': tax_amount,
                                                'base_on': base_on,
                                                'type_line': taxes_lookup[i['id']]['type_line'],
                                                'partner_type': taxes_lookup[i['id']]['partner_type'],
                                                'iva_tax_desc': taxes_lookup[i['id']]['iva_tax_desc'],
                                                'iva_tax_code': taxes_lookup[i['id']]['iva_tax_code'],
                                            }
                                            # Se genera la exoneración si existe para este impuesto
                                            if _tax_exoneration:
                                                _tax_amount_exoneration = round(
                                                    subtotal_line_temp * taxes_lookup[i['id']][
                                                        'exoneration_percentage'] / 100, 5)

                                                if _tax_amount_exoneration == 0.0:
                                                    _tax_amount_exoneration = tax_amount

                                                _line_tax -= _tax_amount_exoneration
                                                _percentage_exoneration = taxes_lookup[i['id']][
                                                                                'exoneration_percentage'] # int(taxes_lookup[i['id']]['exoneration_percentage']) / 100
                                                _percentage_tax = taxes_lookup[i['id']]['tarifa']
                                                tax["exoneracion"] = {
                                                    "montoImpuesto": _tax_amount_exoneration,
                                                    "porcentajeCompra": int(
                                                        taxes_lookup[i['id']]['exoneration_percentage'])
                                                }

                                        taxes[tax_index] = tax
                                        line["impuesto"] = taxes
                                impuestos_arr.append(tax)
                                linea_compras.append({
                                    'neto': subtotal_line if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * subtotal_line,
                                    'impuestos': [tax],
                                    'tipo_inversion': inv_line.tipo_inversion,
                                    'credit_fiscal': inv.credit_fiscal,
                                    'tipo_credit_fiscal': inv.tipo_credit_fiscal,
                                    'gasto_no_dedu': inv.gasto_no_dedu,
                                    'tipo_gasto_no_dedu': inv.tipo_gasto_no_dedu,
                                    'c_sin_imp': inv.c_sin_imp,
                                    'credit_fiscal': inv.credit_fiscal,
                                    'tipo_credit_fiscal': inv.tipo_credit_fiscal,
                                    'gasto_no_dedu': inv.gasto_no_dedu,
                                    'c_sin_imp': self.get_selection_label('account.move', 'c_sin_imp', inv.c_sin_imp),
                                    'csi_ley': inv.csi_ley or '',
                                    'csi_articulo': inv.csi_articulo or '',
                                    'csi_inciso': inv.csi_inciso or '',
                                    'type_line': type_line,
                                    'partner_type': partner_type,
                                })
                                line["impuesto"] = taxes
                                line["impuestoNeto"] = round(_line_tax, 5)

                            # Si no hay uom_id se asume como Servicio
                            if not inv_line.product_uom_id or inv_line.product_uom_id.category_id.name == 'Services' or inv_line.product_id.type == 'service':
                                if taxes:
                                    if _tax_exoneration:
                                        total_servicio_gravado += base_line * (1 - (_tax_amount_exoneration/tax_amount))
                                        total_servicio_exonerado += base_line * (_tax_amount_exoneration/tax_amount)

                                    else:
                                        total_servicio_gravado += base_line

                                    total_impuestos += _line_tax
                                else:
                                    total_servicio_exento += base_line
                            else:
                                if taxes:
                                    if _tax_exoneration:
                                        total_mercaderia_gravado += base_line * (1 - (_tax_amount_exoneration/tax_amount))
                                        total_mercaderia_exonerado += base_line * (_tax_amount_exoneration/tax_amount)

                                    else:
                                        total_mercaderia_gravado += base_line

                                    total_impuestos += _line_tax
                                else:
                                    total_mercaderia_exento += base_line

                            base_subtotal += subtotal_line

                            line["montoTotalLinea"] = round(subtotal_line + _line_tax, 5)

                            lines[line_number] = line
                if total_servicio_salon:
                    total_servicio_salon = round(total_servicio_salon, 5)
                    total_otros_cargos += total_servicio_salon
                    otros_cargos_id += 1
                    otros_cargos[otros_cargos_id] = {
                        'TipoDocumento': '06',
                        'Detalle': escape('Servicio salon 10%'),
                        'MontoCargo': total_servicio_salon
                    }

                total_servicio_gravado = round(total_servicio_gravado, 5)
                total_servicio_exento = round(total_servicio_exento, 5)
                total_servicio_exonerado = round(total_servicio_exonerado, 5)
                total_mercaderia_gravado = round(total_mercaderia_gravado, 5)
                total_mercaderia_exento = round(total_mercaderia_exento, 5)
                total_mercaderia_exonerado = round(total_mercaderia_exonerado, 5)

                total_otros_cargos = round(total_otros_cargos, 5)
                total_iva_devuelto = round(total_iva_devuelto, 5)
                base_subtotal = round(base_subtotal, 5)
                total_impuestos = round(total_impuestos, 5)
                total_descuento = round(total_descuento, 5)

                if wizard_record.doc_clientes == True:
                    datos = {
                        'origen': 'proveedor' if inv.move_type in ['in_invoice', 'in_refund'] else 'cliente',
                        'fecha': datetime.datetime.strptime(str(inv.invoice_date), '%Y-%m-%d').strftime("%d/%m/%Y"),
                        'cliente': inv.partner_id.name,
                        'exonerado': 'SI' if inv.partner_id.has_exoneration == True else 'NO',
                        'actividad_economica': inv.economic_activity_id.code or '',
                        'documento': inv.name,
                        'ref': inv.ref or '',
                        'move_type': inv.move_type,
                        
                        'impuestos': impuestos_arr,
                        'total_servicio_gravado': total_servicio_gravado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_servicio_gravado,
                        'total_servicio_exento': total_servicio_exento if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_servicio_exento,
                        'total_servicio_exonerado': total_servicio_exonerado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_servicio_exonerado,
                        'total_mercaderia_gravado': total_mercaderia_gravado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_mercaderia_gravado,
                        'total_mercaderia_exento': total_mercaderia_exento if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_mercaderia_exento,
                        'total_mercaderia_exonerado': total_mercaderia_exonerado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_mercaderia_exonerado,

                        'total_otros_cargos': total_otros_cargos if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_otros_cargos,
                        'total_iva_devuelto': total_iva_devuelto if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_iva_devuelto,
                        'base_subtotal': base_subtotal if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * base_subtotal,
                        'total_impuestos': total_impuestos if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_impuestos,
                        'total_descuento': total_descuento if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_descuento,

                        'tipo_comprobante': self.get_selection_label('account.move', 'tipo_documento', inv.tipo_documento),
                        'estado_fe': self.get_selection_label('account.move', 'state_tributacion', inv.state_tributacion),
                        'estado': self.get_selection_label('account.move', 'state', inv.state),
                        'estado_pago': self.get_selection_label('account.move', 'payment_state', inv.payment_state),

                        'credit_fiscal': 'SI' if inv.credit_fiscal == True else 'NO',

                        'venta_exentas': inv.venta_exentas,
                        'venta_exentas_descrp': self.get_selection_label('account.move', 'venta_exentas', inv.venta_exentas),
                        'venta_aut_sin_imp': inv.venta_aut_sin_imp,
                        'venta_aut_sin_imp_descrp': self.get_selection_label('account.move', 'venta_aut_sin_imp', inv.venta_aut_sin_imp),
                        'venta_no_sujeta': inv.venta_no_sujeta,
                        'venta_no_sujeta_descrp': self.get_selection_label('account.move', 'venta_no_sujeta', inv.venta_no_sujeta),

                    }
                if wizard_record.doc_proveedores == True:
                    datos = {
                        'origen': 'proveedor' if inv.move_type in ['in_invoice', 'in_refund'] else 'cliente',
                        'fecha': datetime.datetime.strptime(str(inv.invoice_date), '%Y-%m-%d').strftime("%d/%m/%Y"),
                        'cliente': inv.partner_id.name,
                        'exonerado': 'SI' if inv.partner_id.has_exoneration == True else 'NO',
                        'actividad_economica': inv.economic_activity_id.code or '',
                        'documento': inv.name,
                        'ref': inv.ref or '',
                        'move_type': inv.move_type,
                        'impuestos': impuestos_arr,
                        'total_servicio_gravado': total_servicio_gravado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_servicio_gravado,
                        'total_servicio_exento': total_servicio_exento if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_servicio_exento,
                        'total_servicio_exonerado': total_servicio_exonerado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_servicio_exonerado,
                        'total_mercaderia_gravado': total_mercaderia_gravado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_mercaderia_gravado,
                        'total_mercaderia_exento': total_mercaderia_exento if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_mercaderia_exento,
                        'total_mercaderia_exonerado': total_mercaderia_exonerado if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_mercaderia_exonerado,

                        'total_otros_cargos': total_otros_cargos if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_otros_cargos,
                        'total_iva_devuelto': total_iva_devuelto if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_iva_devuelto,
                        'base_subtotal': base_subtotal if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * base_subtotal,
                        'total_impuestos': total_impuestos if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_impuestos,
                        'total_descuento': total_descuento if inv.move_type in ['in_invoice', 'out_invoice'] else -1 * total_descuento,

                        'tipo_comprobante': self.get_selection_label('account.move', 'tipo_documento', inv.tipo_documento),
                        'estado_fe': self.get_selection_label('account.move', 'state_tributacion', inv.state_tributacion),
                        'estado': self.get_selection_label('account.move', 'state', inv.state),
                        'estado_pago': self.get_selection_label('account.move', 'payment_state', inv.payment_state),

                        'credit_fiscal': 'SI' if inv.credit_fiscal == True else 'NO',
                        'tipo_credit_fiscal': self.get_selection_label('account.move', 'tipo_credit_fiscal', (inv.tipo_credit_fiscal or None)),
                        #'tipo_inversion': self.get_selection_label('account.move', 'tipo_inversion', inv.tipo_inversion),

                        'gasto_no_dedu': 'SI' if inv.gasto_no_dedu == True else 'NO',
                        'tipo_gasto_no_dedu': self.get_selection_label('account.move', 'tipo_gasto_no_dedu', (inv.tipo_gasto_no_dedu or None)),
                        'c_sin_imp': self.get_selection_label('account.move', 'c_sin_imp', (inv.c_sin_imp or None)),

                        'csi_ley': inv.csi_ley or '',
                        'csi_articulo': inv.csi_articulo or '',
                        'csi_inciso': inv.csi_inciso or ''

                    }
                #_logger.info('DOCUMENTOS')
                #_logger.info(json.dumps(datos, indent=4, sort_keys=True))
                documentos.append(datos)        
            row = 4

            fila = []
            indice = 0
            tax_ids = []

            for line in documentos:
                for tax in line['impuestos']:
                    tax_ids.append(tax['id'])
            tax_ids = list(dict.fromkeys(tax_ids))

            taxes_company = self.env['account.tax'].sudo().search([('id', 'in', tax_ids)], order='sequence asc')

            #sheet.write(row, 0, 'Origen', format2)
            sheet.write(row, 0, 'Fecha', format2)
            sheet.write(row, 1, 'Cliente', format2)
            sheet.write(row, 2, 'Exonerado', format2)
            sheet.write(row, 3, 'Actividad Económica', format2)
            sheet.write(row, 4, 'Documento', format2)
            sheet.write(row, 5, 'Referencia', format2)
            column = 6
            for tax in taxes_company:
                sheet.write(row, column, tax.name, format5)
                column += 1

            sheet.write(row, column, 'Total Impuestos', format2)
            column += 1
            # Totales
            sheet.write(row, column, 'Total Servicio Gravado', format2)
            column += 1
            for tax in taxes_company:
                title = 'Total Servicio Gravado: ' + tax.name
                sheet.write(row, column, title, format5)
                column += 1
            sheet.write(row, column, 'Total Servicio Exento', format2)
            column += 1
            sheet.write(row, column, 'Total Servicio Exonerado', format2)
            column += 1
            for tax in taxes_company:
                title = 'Total Servicio Exonerado: ' + tax.name
                sheet.write(row, column, title, format5)
                column += 1
            sheet.write(row, column, 'Total Mercadería Gravado', format2)
            column += 1
            for tax in taxes_company:
                title = 'Total Mercadería Gravado: ' + tax.name
                sheet.write(row, column, title, format5)
                column += 1
            sheet.write(row, column, 'Total Mercadería Exento', format2)
            column += 1
            sheet.write(row, column, 'Total Mercadería Exonerado', format2)
            column += 1
            for tax in taxes_company:
                title = 'Total Mercadería Exonerado: ' + tax.name
                sheet.write(row, column, title, format5)
                column += 1
            sheet.write(row, column, 'Total Otros Cargos', format2)
            column += 1
            sheet.write(row, column, 'Total IVA Devuelto', format2)
            column += 1
            sheet.write(row, column, 'Total Base Subtotal', format2)
            column += 1
            sheet.write(row, column, 'Total Descuento', format2)
            
            # Proveedor
            column += 1
            sheet.write(row, column, 'Doc. Elect.', format2)
            column += 1
            sheet.write(row, column, 'Estado FE', format2)
            column += 1
            sheet.write(row, column, 'Estado Odoo', format2)
            column += 1
            sheet.write(row, column, 'Pagos', format2)
            column += 1
            sheet.write(row, column, 'Crédito Fiscal', format2)
            if wizard_record.doc_proveedores == True:
                column += 1
                sheet.write(row, column, 'Tipo Crédito Fiscal', format2)
                #column += 1
                #sheet.write(row, column, 'Tipo de Inversión', format2)


                column += 1
                sheet.write(row, column, 'Gasto no deducible', format2)
                column += 1
                sheet.write(row, column, 'Bienes y servicios con o sin IVA soportado no acreditable', format2)
                column += 1
                sheet.write(row, column, 'Compras autorizadas sin impuesto (órdenes especiales)', format2)
                column += 1
                sheet.write(row, column, 'N° Ley', format2)
                column += 1
                sheet.write(row, column, 'Artículo', format2)
                column += 1
                sheet.write(row, column, 'Insico(si aplica)', format2)

            if wizard_record.doc_clientes == True: 
                column += 1
                sheet.write(row, column, 'Ventas Exentas (Art 8.)', format2)
                column += 1
                sheet.write(row, column, 'Ventas autorizadas sin impuesto (órdenes especiales y otros transitorios)', format2)
                column += 1
                sheet.write(row, column, 'Ventas no sujetas (Art.9)', format2)
            row += 1

            for doc in documentos:
                
                index = 0
                #sheet.write(row, 0, doc['origen'], format3)
                sheet.write(row, 0, doc['fecha'], format3)
                sheet.write(row, 1, doc['cliente'], format3)
                sheet.write(row, 2, doc['exonerado'], format3)
                sheet.write(row, 3, doc['actividad_economica'], format3)
                sheet.write(row, 4, doc['documento'], format3)
                sheet.write(row, 5, doc['ref'], format3)

                column = 6
                for tax in taxes_company:
                    monto = 0.0
                    for line in doc['impuestos']:
                        if line['id'] == tax.id:
                            if doc['move_type'] in ['in_invoice','out_invoice']:
                                monto += line['monto']
                            else:
                                monto += -1 * line['monto']
                    # Resumen para la segunda hoja
                    if indice == 0:
                        fila.insert(len(datos), [monto])
                    else:
                        fila[index].insert(len(fila[index]), monto)
                        index += 1

                    sheet.write(row, column, monto, format4)
                    column += 1
                sheet.write(row, column, doc['total_impuestos'], format4)
                column += 1
                sheet.write(row, column, doc['total_servicio_gravado'], format4)
                column += 1
                # Resumen para la segunda hoja
                if indice == 0:
                        fila.insert(len(datos), [doc['total_impuestos']])
                        fila.insert(len(datos), [doc['total_servicio_gravado']])
                else:
                    fila[index].insert(len(fila[index]), doc['total_impuestos'])
                    index += 1
                    fila[index].insert(len(fila[index]), doc['total_servicio_gravado'])
                    index += 1
                for tax in taxes_company:
                    monto = 0.0
                    for line in doc['impuestos']:
                        if line['id'] == tax.id:
                            if doc['move_type'] in ['in_invoice','out_invoice'] and line['type_line'] == 'servicio':
                                monto += line['base_on']
                            elif doc['move_type'] in ['in_refund' ,'out_refund'] and line['type_line'] == 'servicio':
                                monto += -1 * line['base_on']
                            else:
                                monto = 0.0

                    sheet.write(row, column, monto, format4)
                    column += 1
                    # Resumen para la segunda hoja
                    if indice == 0:
                        fila.insert(len(datos), [monto])
                    else:
                        fila[index].insert(len(fila[index]), monto)
                        index += 1
                sheet.write(row, column, doc['total_servicio_exento'], format4)
                column += 1
                sheet.write(row, column, doc['total_servicio_exonerado'], format4)
                column += 1
                # Resumen para la segunda hoja
                if indice == 0:
                        fila.insert(len(datos), [doc['total_servicio_exento']])
                        fila.insert(len(datos), [doc['total_servicio_exonerado']])
                else:
                    fila[index].insert(len(fila[index]), doc['total_servicio_exento'])
                    index += 1
                    fila[index].insert(len(fila[index]), doc['total_servicio_exonerado'])
                    index += 1
                for tax in taxes_company:
                    monto = 0.0
                    for line in doc['impuestos']:
                        if line['id'] == tax.id:
                            if doc['move_type'] in ['in_invoice','out_invoice'] and line['type_line'] == 'servicio exonerado':
                                monto += line['base_on']
                            elif doc['move_type'] in ['in_refund' ,'out_refund'] and line['type_line'] == 'servicio exonerado':
                                monto += -1 * line['base_on']
                            else:
                                monto = 0.0

                    sheet.write(row, column, monto, format4)
                    column += 1
                    # Resumen para la segunda hoja
                    if indice == 0:
                        fila.insert(len(datos), [monto])
                    else:
                        fila[index].insert(len(fila[index]), monto)
                        index += 1
                sheet.write(row, column, doc['total_mercaderia_gravado'], format4)
                column += 1
                if indice == 0:
                        fila.insert(len(datos), [doc['total_mercaderia_gravado']])
                else:
                    fila[index].insert(len(fila[index]), doc['total_mercaderia_gravado'])
                    index += 1
                for tax in taxes_company:
                    monto = 0.0
                    for line in doc['impuestos']:
                        if line['id'] == tax.id:
                            if doc['move_type'] in ['in_invoice','out_invoice'] and line['type_line'] == 'mercaderia':
                                monto += line['base_on']
                            elif doc['move_type'] in ['in_refund' ,'out_refund'] and line['type_line'] == 'mercaderia':
                                monto += -1 * line['base_on']
                            else:
                                monto = 0.0

                    sheet.write(row, column, monto, format4)
                    column += 1
                    # Resumen para la segunda hoja
                    if indice == 0:
                        fila.insert(len(datos), [monto])
                    else:
                        fila[index].insert(len(fila[index]), monto)
                        index += 1
                sheet.write(row, column, doc['total_mercaderia_exento'], format4)
                column += 1
                sheet.write(row, column, doc['total_mercaderia_exonerado'], format4)
                column += 1
                if indice == 0:
                        fila.insert(len(datos), [doc['total_mercaderia_exento']])
                        fila.insert(len(datos), [doc['total_mercaderia_exonerado']])
                else:
                    fila[index].insert(len(fila[index]), doc['total_mercaderia_exento'])
                    index += 1
                    fila[index].insert(len(fila[index]), doc['total_mercaderia_exonerado'])
                    index += 1
                for tax in taxes_company:
                    monto = 0.0
                    for line in doc['impuestos']:
                        if line['id'] == tax.id:
                            if doc['move_type'] in ['in_invoice','out_invoice'] and line['type_line'] == 'mercaderia exonerado':
                                monto += line['base_on']
                            elif doc['move_type'] in ['in_refund' ,'out_refund'] and line['type_line'] == 'mercaderia exonerado':
                                monto += -1 * line['base_on']
                            else:
                                monto = 0.0

                    sheet.write(row, column, monto, format4)
                    column += 1
                    # Resumen para la segunda hoja
                    if indice == 0:
                        fila.insert(len(datos), [monto])
                    else:
                        fila[index].insert(len(fila[index]), monto)
                        index += 1
                sheet.write(row, column, doc['total_otros_cargos'], format4)
                column += 1
                sheet.write(row, column, doc['total_iva_devuelto'], format4)
                column += 1
                sheet.write(row, column, doc['base_subtotal'], format4)
                column += 1
                sheet.write(row, column, doc['total_descuento'], format4)

                if indice == 0:
                        fila.insert(len(datos), [doc['total_otros_cargos']])
                        fila.insert(len(datos), [doc['total_iva_devuelto']])
                        fila.insert(len(datos), [doc['base_subtotal']])
                        fila.insert(len(datos), [doc['total_descuento']])
                else:
                    fila[index].insert(len(fila[index]), doc['total_otros_cargos'])
                    index += 1
                    fila[index].insert(len(fila[index]), doc['total_iva_devuelto'])
                    index += 1
                    fila[index].insert(len(fila[index]), doc['base_subtotal'])
                    index += 1
                    fila[index].insert(len(fila[index]), doc['total_descuento'])
                    index += 1
                indice += 1

                # Proveedor
                column += 1
                sheet.write(row, column, doc['tipo_comprobante'], format3)
                column += 1
                sheet.write(row, column, doc['estado_fe'], format3)
                column += 1
                sheet.write(row, column, doc['estado'], format3)
                column += 1
                sheet.write(row, column, doc['estado_pago'], format3)
                column += 1
                sheet.write(row, column, doc['credit_fiscal'], format3)
                if doc['origen'] == 'proveedor':
                    column += 1
                    sheet.write(row, column, doc['tipo_credit_fiscal'], format3)
                    #column += 1
                    #sheet.write(row, column, doc['tipo_inversion'], format3)

                    column += 1
                    sheet.write(row, column, doc['gasto_no_dedu'], format3)
                    column += 1
                    sheet.write(row, column, doc['tipo_gasto_no_dedu'], format3)
                    column += 1
                    sheet.write(row, column, doc['c_sin_imp'], format3)
                    column += 1
                    sheet.write(row, column, doc['csi_ley'], format3)
                    column += 1
                    sheet.write(row, column, doc['csi_articulo'], format3)
                    column += 1
                    sheet.write(row, column, doc['csi_inciso'], format3)
                if doc['origen'] == 'cliente':
                    
                    column += 1
                    sheet.write(row, column, doc['venta_exentas_descrp'], format3)
                    column += 1
                    sheet.write(row, column, doc['venta_aut_sin_imp_descrp'], format3)
                    column += 1
                    sheet.write(row, column, doc['venta_no_sujeta_descrp'], format3)
                row += 1
            row += 4
                
            sheet.hide_gridlines(2)

            if wizard_record.doc_clientes == True and len(documentos) > 0:
                sheet2 = workbook.add_worksheet("Resumen Reporte Facturación")

                sheet2.write(0, 0, 'Fecha Inicio', format2)
                sheet2.write(0, 1, inicio, format3)
                sheet2.write(0, 2, 'Fecha Final', format2)
                sheet2.write(0, 3, fin, format3)
                column = 0

                tax_ids = []

                for line in documentos:
                    for tax in line['impuestos']:
                        tax_ids.append(tax['id'])
                tax_ids = list(dict.fromkeys(tax_ids))

                taxes_company = self.env['account.tax'].sudo().search([('id', 'in', tax_ids)], order='sequence asc')

                row = 4
                for tax in taxes_company:
                    sheet2.write(row, column, tax.name, format2)
                    row += 1

                sheet2.write(row, column, 'Total Impuestos', format2)
                row += 1
                # Totales
                sheet2.write(row, column, 'Total Servicio Gravado', format2)
                row += 1
                for tax in taxes_company:
                    title = 'Total Servicio Gravado: ' + tax.name
                    sheet2.write(row, column, title, format2)
                    row += 1
                sheet2.write(row, column, 'Total Servicio Exento', format2)
                row += 1
                sheet2.write(row, column, 'Total Servicio Exonerado', format2)
                row += 1
                for tax in taxes_company:
                    title = 'Total Servicio Exonerado: ' + tax.name
                    sheet2.write(row, column, title, format2)
                    row += 1
                sheet2.write(row, column, 'Total Mercadería Gravado', format2)
                row += 1
                for tax in taxes_company:
                    title = 'Total Mercadería Gravado: ' + tax.name
                    sheet2.write(row, column, title, format2)
                    row += 1
                sheet2.write(row, column, 'Total Mercadería Exento', format2)
                row += 1
                sheet2.write(row, column, 'Total Mercadería Exonerado', format2)
                row += 1
                for tax in taxes_company:
                    title = 'Total Mercadería Exonerado: ' + tax.name
                    sheet2.write(row, column, title, format2)
                    row += 1
                sheet2.write(row, column, 'Total Otros Cargos', format2)
                row += 1
                sheet2.write(row, column, 'Total IVA Devuelto', format2)
                row += 1
                sheet2.write(row, column, 'Total Base Subtotal', format2)
                row += 1
                sheet2.write(row, column, 'Total Descuento', format2)
                

                column = 1
                row = 4
                for dato in fila:
                    sheet2.write(row, column, sum(dato), format4)
                    row +=1
                    

                
                row += 2

                sheet2.write(row, 1, '1%', format5)
                sheet2.write(row, 2, '2%', format5)
                sheet2.write(row, 3, '4%', format5)
                sheet2.write(row, 4, '8%', format5)
                sheet2.write(row, 5, '13%', format5)
                sheet2.write(row, 6, 'Total', format5)

                """Calculo de detalle"""

                venta_aut_sin_imp = []
                venta_exentas = []
                venta_no_sujeta = []

                for line in documentos:
                    if  line['venta_aut_sin_imp'] != False:
                        venta_aut_sin_imp.append({
                            'code': line['venta_aut_sin_imp'],
                            'description': line['venta_aut_sin_imp_descrp'],
                            'total_impuestos': line['total_impuestos'],
                            'impuestos': line['impuestos'],
                            'credit_fiscal': line['credit_fiscal']
                        })
                    elif  line['venta_exentas'] != False:
                        venta_exentas.append({
                            'code': line['venta_exentas'],
                            'description': line['venta_exentas_descrp'],
                            'total_impuestos': line['total_impuestos'],
                            'impuestos': line['impuestos'],
                            'credit_fiscal': line['credit_fiscal']
                        })
                    elif  line['venta_no_sujeta'] != False:
                        venta_no_sujeta.append({
                            'code': line['venta_no_sujeta'],
                            'description': line['venta_no_sujeta_descrp'],
                            'total_impuestos': line['total_impuestos'],
                            'impuestos': line['impuestos'],
                            'credit_fiscal': line['credit_fiscal']
                        })


                column = 0
                row += 1

                format2_title = workbook.add_format({'font_size': 14, 'bold': True, 'bg_color': '#00A09D', 'font_color': 'white'})
                format7 = workbook.add_format({'font_size': 12, 'bold': True, 'bg_color': '#8F8F8F', 'font_color': 'white'})

                sheet2.write(row, column, 'Genera Crédito Fiscal', format2_title)
                sheet2.write(row, 1, '', format2_title)
                sheet2.write(row, 2, '', format2_title)
                sheet2.write(row, 3, '', format2_title)
                sheet2.write(row, 4, '', format2_title)
                sheet2.write(row, 5, '', format2_title)
                sheet2.write(row, 6, '', format2_title)
                monto = 0.0



                column = 0
                row += 1
                sheet2.write(row, column, 'Ventas Exentas (Art 8.)', format2)

                tax_1 = 0.0
                tax_2 = 0.0
                tax_4 = 0.0
                tax_8 = 0.0
                tax_13 = 0.0
                for line in venta_exentas:
                    if line['credit_fiscal'] == 'SI':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']
                sheet2.write(row, 1, tax_1, negrita_numero_border)
                sheet2.write(row, 2, tax_2, negrita_numero_border)
                sheet2.write(row, 3, tax_4, negrita_numero_border)
                sheet2.write(row, 4, tax_8, negrita_numero_border)
                sheet2.write(row, 5, tax_13, negrita_numero_border)
                sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), negrita_numero_border)

                

                for line in venta_exentas:
                    row +=1
                    sheet2.write(row, 0, line['description'], format7)
                    tax_1 = 0.0
                    tax_2 = 0.0
                    tax_4 = 0.0
                    tax_8 = 0.0
                    tax_13 = 0.0

                    if line['credit_fiscal'] == 'SI':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']


                    sheet2.write(row, 1, tax_1, format4)
                    sheet2.write(row, 2, tax_2, format4)
                    sheet2.write(row, 3, tax_4, format4)
                    sheet2.write(row, 4, tax_8, format4)
                    sheet2.write(row, 5, tax_13, format4)
                    sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), format4)

                column = 0
                row += 2
                sheet2.write(row, column, 'Ventas autorizadas sin impuesto (órdenes especiales y otros transitorios)', format2)

                tax_1 = 0.0
                tax_2 = 0.0
                tax_4 = 0.0
                tax_8 = 0.0
                tax_13 = 0.0
                for line in venta_aut_sin_imp:
                    if line['credit_fiscal'] == 'SI':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']
                sheet2.write(row, 1, tax_1, negrita_numero_border)
                sheet2.write(row, 2, tax_2, negrita_numero_border)
                sheet2.write(row, 3, tax_4, negrita_numero_border)
                sheet2.write(row, 4, tax_8, negrita_numero_border)
                sheet2.write(row, 5, tax_13, negrita_numero_border)
                sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), negrita_numero_border)

                for line in venta_aut_sin_imp:
                    row +=1
                    sheet2.write(row, 0, line['description'], format7)
                    tax_1 = 0.0
                    tax_2 = 0.0
                    tax_4 = 0.0
                    tax_8 = 0.0
                    tax_13 = 0.0

                    if line['credit_fiscal'] == 'SI':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']


                    sheet2.write(row, 1, tax_1, format4)
                    sheet2.write(row, 2, tax_2, format4)
                    sheet2.write(row, 3, tax_4, format4)
                    sheet2.write(row, 4, tax_8, format4)
                    sheet2.write(row, 5, tax_13, format4)
                    sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), format4)


                column = 0
                row += 2
                sheet2.write(row, column, 'Ventas no sujetas (Art.9)', format2)

                tax_1 = 0.0
                tax_2 = 0.0
                tax_4 = 0.0
                tax_8 = 0.0
                tax_13 = 0.0
                for line in venta_no_sujeta:
                    if line['credit_fiscal'] == 'SI':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']
                sheet2.write(row, 1, tax_1, negrita_numero_border)
                sheet2.write(row, 2, tax_2, negrita_numero_border)
                sheet2.write(row, 3, tax_4, negrita_numero_border)
                sheet2.write(row, 4, tax_8, negrita_numero_border)
                sheet2.write(row, 5, tax_13, negrita_numero_border)
                sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), negrita_numero_border)

                for line in venta_no_sujeta:
                    row +=1
                    sheet2.write(row, 0, line['description'], format7)
                    tax_1 = 0.0
                    tax_2 = 0.0
                    tax_4 = 0.0
                    tax_8 = 0.0
                    tax_13 = 0.0

                    if line['credit_fiscal'] == 'SI':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']


                    sheet2.write(row, 1, tax_1, format4)
                    sheet2.write(row, 2, tax_2, format4)
                    sheet2.write(row, 3, tax_4, format4)
                    sheet2.write(row, 4, tax_8, format4)
                    sheet2.write(row, 5, tax_13, format4)
                    sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), format4)


                """ SIN CREDITO FISCAL """
                column = 0
                row += 3

                sheet2.write(row, 1, '1%', format5)
                sheet2.write(row, 2, '2%', format5)
                sheet2.write(row, 3, '4%', format5)
                sheet2.write(row, 4, '8%', format5)
                sheet2.write(row, 5, '13%', format5)
                sheet2.write(row, 6, 'Total', format5)
                row += 1

                sheet2.write(row, column, 'No Genera Crédito Fiscal', format2_title)
                sheet2.write(row, 1, '', format2_title)
                sheet2.write(row, 2, '', format2_title)
                sheet2.write(row, 3, '', format2_title)
                sheet2.write(row, 4, '', format2_title)
                sheet2.write(row, 5, '', format2_title)
                sheet2.write(row, 6, '', format2_title)
                monto = 0.0



                column = 0
                row += 1
                sheet2.write(row, column, 'Ventas Exentas (Art 8.)', format2)

                tax_1 = 0.0
                tax_2 = 0.0
                tax_4 = 0.0
                tax_8 = 0.0
                tax_13 = 0.0
                for line in venta_exentas:
                    if line['credit_fiscal'] == 'NO':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']
                sheet2.write(row, 1, tax_1, negrita_numero_border)
                sheet2.write(row, 2, tax_2, negrita_numero_border)
                sheet2.write(row, 3, tax_4, negrita_numero_border)
                sheet2.write(row, 4, tax_8, negrita_numero_border)
                sheet2.write(row, 5, tax_13, negrita_numero_border)
                sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), negrita_numero_border)

                

                for line in venta_exentas:
                    row +=1
                    sheet2.write(row, 0, line['description'], format7)
                    tax_1 = 0.0
                    tax_2 = 0.0
                    tax_4 = 0.0
                    tax_8 = 0.0
                    tax_13 = 0.0

                    if line['credit_fiscal'] == 'NO':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']


                    sheet2.write(row, 1, tax_1, format4)
                    sheet2.write(row, 2, tax_2, format4)
                    sheet2.write(row, 3, tax_4, format4)
                    sheet2.write(row, 4, tax_8, format4)
                    sheet2.write(row, 5, tax_13, format4)
                    sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), format4)

                column = 0
                row += 2
                sheet2.write(row, column, 'Ventas autorizadas sin impuesto (órdenes especiales y otros transitorios)', format2)

                tax_1 = 0.0
                tax_2 = 0.0
                tax_4 = 0.0
                tax_8 = 0.0
                tax_13 = 0.0
                for line in venta_aut_sin_imp:
                    if line['credit_fiscal'] == 'NO':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']
                sheet2.write(row, 1, tax_1, negrita_numero_border)
                sheet2.write(row, 2, tax_2, negrita_numero_border)
                sheet2.write(row, 3, tax_4, negrita_numero_border)
                sheet2.write(row, 4, tax_8, negrita_numero_border)
                sheet2.write(row, 5, tax_13, negrita_numero_border)
                sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), negrita_numero_border)

                for line in venta_aut_sin_imp:
                    row +=1
                    sheet2.write(row, 0, line['description'], format7)
                    tax_1 = 0.0
                    tax_2 = 0.0
                    tax_4 = 0.0
                    tax_8 = 0.0
                    tax_13 = 0.0

                    if line['credit_fiscal'] == 'NO':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']


                    sheet2.write(row, 1, tax_1, format4)
                    sheet2.write(row, 2, tax_2, format4)
                    sheet2.write(row, 3, tax_4, format4)
                    sheet2.write(row, 4, tax_8, format4)
                    sheet2.write(row, 5, tax_13, format4)
                    sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), format4)


                column = 0
                row += 2
                sheet2.write(row, column, 'Ventas no sujetas (Art.9)', format2)

                tax_1 = 0.0
                tax_2 = 0.0
                tax_4 = 0.0
                tax_8 = 0.0
                tax_13 = 0.0
                for line in venta_no_sujeta:
                    if line['credit_fiscal'] == 'NO':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']
                sheet2.write(row, 1, tax_1, negrita_numero_border)
                sheet2.write(row, 2, tax_2, negrita_numero_border)
                sheet2.write(row, 3, tax_4, negrita_numero_border)
                sheet2.write(row, 4, tax_8, negrita_numero_border)
                sheet2.write(row, 5, tax_13, negrita_numero_border)
                sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), negrita_numero_border)

                for line in venta_no_sujeta:
                    row +=1
                    sheet2.write(row, 0, line['description'], format7)
                    tax_1 = 0.0
                    tax_2 = 0.0
                    tax_4 = 0.0
                    tax_8 = 0.0
                    tax_13 = 0.0

                    if line['credit_fiscal'] == 'NO':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 1.0:
                                tax_1 += tax['monto']
                            if tax['tarifa'] == 2.0:
                                tax_2 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                tax_4 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                tax_8 += tax['monto']
                            if tax['tarifa'] == 13.0:
                                tax_13 += tax['monto']


                    sheet2.write(row, 1, tax_1, format4)
                    sheet2.write(row, 2, tax_2, format4)
                    sheet2.write(row, 3, tax_4, format4)
                    sheet2.write(row, 4, tax_8, format4)
                    sheet2.write(row, 5, tax_13, format4)
                    sheet2.write(row, 6, (tax_1 + tax_2 + tax_4 + tax_8 + tax_13), format4)

                sheet2.hide_gridlines(2)
            if wizard_record.doc_proveedores == True and len(documentos) > 0:

                sheet2 = workbook.add_worksheet("Resumen Reporte Facturación")

                sheet2.write(0, 0, 'Fecha Inicio', format2)
                sheet2.write(0, 1, inicio, format3)
                sheet2.write(0, 2, 'Fecha Final', format2)
                sheet2.write(0, 3, fin, format3)
                column = 0

                compra_bien_local = 0.0
                bienes_capital_local = 0.0
                gastos_servicios_local = 0.0

                compra_bien_exterior = 0.0
                bienes_capital_exterior = 0.0
                gastos_servicios_exterior = 0.0

                tax_compra_bien_local = 0.0
                tax_bienes_capital_local = 0.0
                tax_gastos_servicios_local = 0.0

                tax_compra_bien_exterior = 0.0
                tax_bienes_capital_exterior = 0.0
                tax_gastos_servicios_exterior = 0.0

                total_reporte = 0.0
                for line in linea_compras:
                    if line['tipo_inversion'] == 'compra_b_l':
                        compra_bien_local += line['neto']
                        for tax in line['impuestos']:
                            tax_compra_bien_local += tax['monto']

                    if line['tipo_inversion'] == 'bienes_c_l':
                        bienes_capital_local += line['neto']
                        for tax in line['impuestos']:
                            tax_bienes_capital_local += tax['monto']
                    
                    if line['tipo_inversion'] == 'gasto_s_l':
                        gastos_servicios_local += line['neto']
                        for tax in line['impuestos']:
                            tax_gastos_servicios_local += tax['monto']

                    if line['tipo_inversion'] == 'compra_b_e':
                        compra_bien_exterior += line['neto']
                        for tax in line['impuestos']:
                            tax_compra_bien_exterior += tax['monto']
                    
                    if line['tipo_inversion'] == 'bienes_c_e':
                        bienes_capital_exterior += line['neto']
                        for tax in line['impuestos']:
                            tax_bienes_capital_exterior += tax['monto']

                    if line['tipo_inversion'] == 'gasto_s_e':
                        gastos_servicios_exterior += line['neto']
                        for tax in line['impuestos']:
                            tax_gastos_servicios_exterior += tax['monto']

                    total_reporte += line['neto']
                
                '''
                    RESUMEN
                '''
                sheet2.write(3, 1, 'Total', format5)
                sheet2.write(3, 2, '%', format5)
                sheet2.write(3, 3, 'I.V.A.', format5)


                row = 4
                sheet2.write(row, column, 'Compra de bienes-Local', format2)
                sheet2.write(row, column + 1, compra_bien_local, format4)
                if compra_bien_local > 0:
                    sheet2.write(row, column + 2, (compra_bien_local/total_reporte), format6)
                else:
                    sheet2.write(row, column + 2, 0, format6)
                sheet2.write(row, column + 3, tax_compra_bien_local, format4)
                row += 1


                sheet2.write(row, column, 'Bienes de Capital-Local', format2)
                sheet2.write(row, column + 1, bienes_capital_local, format4)
                sheet2.write(row, column + 2, (bienes_capital_local/total_reporte), format6)
                if compra_bien_local > 0:
                    sheet2.write(row, column + 2, (compra_bien_local/total_reporte), format6)
                else:
                    sheet2.write(row, column + 2, 0, format6)
                sheet2.write(row, column + 3, tax_bienes_capital_local, format4)
                row += 1


                sheet2.write(row, column, 'Gastos por servicios-Local', format2)
                sheet2.write(row, column + 1, gastos_servicios_local, format4)
                sheet2.write(row, column + 2, (gastos_servicios_local/total_reporte), format6)
                if gastos_servicios_local > 0:
                    sheet2.write(row, column + 2, (gastos_servicios_local/total_reporte), format6)
                else:
                    sheet2.write(row, column + 2, 0, format6)
                sheet2.write(row, column + 3, tax_gastos_servicios_local, format4)
                row += 1


                sheet2.write(row, column, 'Compra de bienes-Exterior', format2)
                sheet2.write(row, column + 1, compra_bien_exterior, format4)
                sheet2.write(row, column + 2, (compra_bien_exterior/total_reporte), format6)
                if compra_bien_exterior > 0:
                    sheet2.write(row, column + 2, (compra_bien_exterior/total_reporte), format6)
                else:
                    sheet2.write(row, column + 2, 0, format6)
                sheet2.write(row, column + 3, tax_compra_bien_exterior, format4)
                row += 1


                sheet2.write(row, column, 'Bienes de Capital-Exterior', format2)
                sheet2.write(row, column + 1, bienes_capital_exterior, format4)
                sheet2.write(row, column + 2, (bienes_capital_exterior/total_reporte), format6)
                if bienes_capital_exterior > 0:
                    sheet2.write(row, column + 2, (bienes_capital_exterior/total_reporte), format6)
                else:
                    sheet2.write(row, column + 2, 0, format6)
                sheet2.write(row, column + 3, tax_bienes_capital_exterior, format4)
                row += 1


                sheet2.write(row, column, 'Gastos por servicios-Exterior', format2)
                sheet2.write(row, column + 1, gastos_servicios_exterior, format4)
                sheet2.write(row, column + 2, (gastos_servicios_exterior/total_reporte), format6)
                if gastos_servicios_exterior > 0:
                    sheet2.write(row, column + 2, (gastos_servicios_exterior/total_reporte), format6)
                else:
                    sheet2.write(row, column + 2, 0, format6)
                sheet2.write(row, column + 3, tax_gastos_servicios_exterior, format4)
                row += 4

                '''
                    DETALLE
                '''
                # *****IVA Soportado-LOCAL
                c1_1 = 0.0
                c1_2 = 0.0
                ### Resumen C1_2
                c1_2_tax_1 = 0.0
                c1_2_tax_4 = 0.0
                c1_2_tax_8 = 0.0
                c1_2_tax_13 = 0.0

                c1_3 = 0.0
                ### Resumen C1_2
                c1_3_tax_1 = 0.0
                c1_3_tax_4 = 0.0
                c1_3_tax_8 = 0.0
                c1_3_tax_13 = 0.0

                c1_4 = 0.0
                ### Resumen C1_2
                c1_4_tax_1 = 0.0
                c1_4_tax_4 = 0.0
                c1_4_tax_8 = 0.0
                c1_4_tax_13 = 0.0
                
                

                # *****Compras con IVA soportado acreditable-LOCAL
                c2_1 = 0.0
                c2_2 = 0.0
                ### Resumen C2_2
                c2_2_tax_1 = 0.0
                c2_2_tax_4 = 0.0
                c2_2_tax_8 = 0.0
                c2_2_tax_13 = 0.0

                c2_3 = 0.0
                ### Resumen C2_3
                c2_3_tax_1 = 0.0
                c2_3_tax_4 = 0.0
                c2_3_tax_8 = 0.0
                c2_3_tax_13 = 0.0

                c2_4 = 0.0
                ### Resumen C2_4
                c2_4_tax_1 = 0.0
                c2_4_tax_4 = 0.0
                c2_4_tax_8 = 0.0
                c2_4_tax_13 = 0.0

                # *****IVA Soportado-EXTERIOR
                c3_1 = 0.0
                c3_2 = 0.0
                ### Resumen C3_4
                c3_2_tax_1 = 0.0
                c3_2_tax_4 = 0.0
                c3_2_tax_8 = 0.0
                c3_2_tax_13 = 0.0

                c3_3 = 0.0
                ### Resumen C3_4
                c3_3_tax_1 = 0.0
                c3_3_tax_4 = 0.0
                c3_3_tax_8 = 0.0
                c3_3_tax_13 = 0.0
                
                c3_4 = 0.0
                ### Resumen C3_4
                c3_4_tax_1 = 0.0
                c3_4_tax_4 = 0.0
                c3_4_tax_8 = 0.0
                c3_4_tax_13 = 0.0

                # *****Compras con IVA soportado acreditable-EXTERIOR
                c4_1 = 0.0
                c4_2 = 0.0
                ### Resumen C4_2
                c4_2_tax_1 = 0.0
                c4_2_tax_4 = 0.0
                c4_2_tax_8 = 0.0
                c4_2_tax_13 = 0.0
                
                c4_3 = 0.0
                ### Resumen C4_3
                c4_3_tax_1 = 0.0
                c4_3_tax_4 = 0.0
                c4_3_tax_8 = 0.0
                c4_3_tax_13 = 0.0
                
                c4_4 = 0.0
                ### Resumen C4_4
                c4_4_tax_1 = 0.0
                c4_4_tax_4 = 0.0
                c4_4_tax_8 = 0.0
                c4_4_tax_13 = 0.0

                # ******Compras sin IVA soportado y/o con IVA soportado no acreditable
                c5_1 = 0.0
                c5_2 = 0.0
                ### Resumen C5_2
                c5_2_tax_1 = 0.0
                c5_2_tax_4 = 0.0
                c5_2_tax_8 = 0.0
                c5_2_tax_13 = 0.0

                c5_3 = 0.0
                ### Resumen C5_3
                c5_3_tax_1 = 0.0
                c5_3_tax_4 = 0.0
                c5_3_tax_8 = 0.0
                c5_3_tax_13 = 0.0

                c5_4 = 0.0
                ### Resumen C5_4
                c5_4_tax_1 = 0.0
                c5_4_tax_4 = 0.0
                c5_4_tax_8 = 0.0
                c5_4_tax_13 = 0.0

                c5_5 = 0.0
                ### Resumen C5_5
                c5_5_tax_1 = 0.0
                c5_5_tax_4 = 0.0
                c5_5_tax_8 = 0.0
                c5_5_tax_13 = 0.0

                for line in linea_compras:

                    '''
                    IVA Soportado-LOCAL
                    '''
                    if line['gasto_no_dedu'] == True and line['credit_fiscal'] == False and line['partner_type'] == 'local' and line['tipo_inversion'] == 'compra_b_l':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c1_2_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c1_2_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c1_2_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c1_2_tax_1 += tax['monto']
                            c1_2 += tax['monto']
                        
                    if line['gasto_no_dedu'] == True and line['credit_fiscal'] == False and line['partner_type'] == 'local' and line['tipo_inversion'] == 'bienes_c_l':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c1_3_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c1_3_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c1_3_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c1_3_tax_1 += tax['monto']
                            c1_3 += tax['monto']

                    if line['gasto_no_dedu'] == True and line['credit_fiscal'] == False and line['partner_type'] == 'local' and line['tipo_inversion'] == 'gasto_s_l':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c1_4_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c1_4_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c1_4_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c1_4_tax_1 += tax['monto']
                            c1_4 += tax['monto']

                    '''
                    Compras con IVA soportado acreditable-LOCAL
                    '''
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == True and line['partner_type'] == 'local' and line['tipo_inversion'] == 'compra_b_l':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c2_2_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c2_2_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c2_2_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c2_2_tax_1 += tax['monto']
                            c2_2 += tax['monto']

                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == True and line['partner_type'] == 'local' and line['tipo_inversion'] == 'bienes_c_l':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c2_3_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c2_3_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c2_3_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c2_3_tax_1 += tax['monto']
                            c2_3 += tax['monto']
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == True and line['partner_type'] == 'local' and line['tipo_inversion'] == 'gasto_s_l':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c2_4_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c2_4_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c2_4_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c2_4_tax_1 += tax['monto']
                            c2_4 += tax['monto']

                    '''
                    IVA Soportado-EXTERIOR
                    '''
                    if line['gasto_no_dedu'] == True and line['credit_fiscal'] == False and line['partner_type'] == 'exterior' and line['tipo_inversion'] == 'compra_b_e':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c3_2_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c3_2_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c3_2_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c3_2_tax_1 += tax['monto']
                            c3_2 += tax['monto']
                    if line['gasto_no_dedu'] == True and line['credit_fiscal'] == False and line['partner_type'] == 'exterior' and line['tipo_inversion'] == 'bienes_c_e':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c3_3_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c3_3_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c3_3_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c3_3_tax_1 += tax['monto']
                            c3_3 += tax['monto']
                    if line['gasto_no_dedu'] == True and line['credit_fiscal'] == False and line['partner_type'] == 'exterior' and line['tipo_inversion'] == 'gasto_s_e':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c3_4_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c3_4_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c3_4_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c3_4_tax_1 += tax['monto']
                            c3_4 += tax['monto']

                    '''
                    Compras con IVA soportado acreditable-EXTERIOR
                    '''
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == True and line['partner_type'] == 'exterior' and line['tipo_inversion'] == 'compra_b_e':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c4_2_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c4_2_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c4_2_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c4_2_tax_1 += tax['monto']
                            c4_2 += tax['monto']
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == True and line['partner_type'] == 'exterior' and line['tipo_inversion'] == 'bienes_c_e':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c3_3_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c4_3_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c4_3_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c4_3_tax_1 += tax['monto']
                            c4_3 += tax['monto']
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == True and line['partner_type'] == 'exterior' and line['tipo_inversion'] == 'gasto_s_e':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c4_4_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c4_4_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c4_4_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c4_4_tax_1 += tax['monto']
                            c4_4 += tax['monto']

                    '''
                    Compras sin IVA soportado y/o con IVA soportado no acreditable
                    '''
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == False and line['partner_type'] == 'local' and line['type_line'] in ['servicio', 'mercaderia'] and line['tipo_credit_fiscal'] == 'exenciones':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c5_2_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c5_2_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c5_2_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c5_2_tax_1 += tax['monto']
                            c5_2 += tax['monto']
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == False and line['partner_type'] == 'exterior' and line['type_line'] in ['servicio', 'mercaderia'] and line['tipo_credit_fiscal'] == 'exenciones':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c5_3_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c5_3_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c5_3_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c5_3_tax_1 += tax['monto']
                            c5_3 += tax['monto']
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == False and line['partner_type'] == 'local' and line['type_line'] in ['servicio', 'mercaderia'] and line['tipo_credit_fiscal'] == 'no_sujecion':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c5_4_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c5_4_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c5_4_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c5_4_tax_1 += tax['monto']
                            c5_4 += tax['monto']
                    if line['gasto_no_dedu'] == False and line['credit_fiscal'] == False and line['partner_type'] == 'exterior' and line['type_line'] in ['servicio', 'mercaderia'] and line['tipo_credit_fiscal'] == 'no_sujecion':
                        for tax in line['impuestos']:
                            if tax['tarifa'] == 13.0:
                                c5_5_tax_13 += tax['monto']
                            if tax['tarifa'] == 8.0:
                                c5_5_tax_8 += tax['monto']
                            if tax['tarifa'] == 4.0:
                                c5_5_tax_4 += tax['monto']
                            if tax['tarifa'] == 1.0:
                                c5_5_tax_1 += tax['monto']
                            c5_5 += tax['monto']

                #SUBTOTALES
                c1_1 = (c1_2 + c1_3 + c1_4)
                c2_1 = (c2_2 + c2_3 + c2_4)
                c3_1 = (c3_2 + c3_3 + c3_4 )
                c4_1 = (c4_2 + c4_3 + c4_4)
                c5_1 = (c5_2 + c5_3 + c5_4 + c5_5)

                
                sheet2.write(row, 1, 'TOTAL', format5)
                sheet2.write(row, 2, '1%', format5)
                sheet2.write(row, 3, '4%', format5)
                sheet2.write(row, 4, '8%', format5)
                sheet2.write(row, 5, '13%', format5)
                row += 1

                sheet2.write(row, column, 'IVA Soportado-LOCAL', format2)
                sheet2.write(row, column + 1, c1_1, negrita_numero_border)
                sheet2.write(row, 2, (c1_2_tax_1 + c1_3_tax_1 + c1_4_tax_1), negrita_numero_border)
                sheet2.write(row, 3, (c1_2_tax_4 + c1_3_tax_4 + c1_4_tax_4), negrita_numero_border)
                sheet2.write(row, 4, (c1_2_tax_8 + c1_3_tax_8 + c1_4_tax_8), negrita_numero_border)
                sheet2.write(row, 5, (c1_2_tax_13 + c1_3_tax_13 + c1_4_tax_13), negrita_numero_border)
                row +=1
                sheet2.write(row, column, 'Compra de bienes-Local', format5)
                sheet2.write(row, 1, c1_2, negrita_numero)
                sheet2.write(row, 2, c1_2_tax_1, format4)
                sheet2.write(row, 3, c1_2_tax_4, format4)
                sheet2.write(row, 4, c1_2_tax_8, format4)
                sheet2.write(row, 5, c1_2_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Bienes de Capital-Local', format5)
                sheet2.write(row, column + 1, c1_3, negrita_numero)
                sheet2.write(row, 2, c1_3_tax_1, format4)
                sheet2.write(row, 3, c1_3_tax_4, format4)
                sheet2.write(row, 4, c1_3_tax_8, format4)
                sheet2.write(row, 5, c1_3_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Gastos por servicios-Local', format5)
                sheet2.write(row, column + 1, c1_4, negrita_numero)
                sheet2.write(row, 2, c1_4_tax_1, format4)
                sheet2.write(row, 3, c1_4_tax_4, format4)
                sheet2.write(row, 4, c1_4_tax_8, format4)
                sheet2.write(row, 5, c1_4_tax_13, format4)
                row +=2

                sheet2.write(row, column, 'Compras con IVA soportado acreditable-LOCAL', format2)
                sheet2.write(row, column + 1, c2_1, negrita_numero_border)
                sheet2.write(row, 2, (c2_2_tax_1 + c2_3_tax_1 + c2_4_tax_1), negrita_numero_border)
                sheet2.write(row, 3, (c2_2_tax_4 + c2_3_tax_4 + c2_4_tax_4), negrita_numero_border)
                sheet2.write(row, 4, (c2_2_tax_8 + c2_3_tax_8 + c2_4_tax_8), negrita_numero_border)
                sheet2.write(row, 5, (c2_2_tax_13 + c2_3_tax_13 + c2_4_tax_13), negrita_numero_border)
                row +=1
                sheet2.write(row, column, 'Compra de bienes-Local', format5)
                sheet2.write(row, column + 1, c2_2, negrita_numero)
                sheet2.write(row, 2, c2_2_tax_1, format4)
                sheet2.write(row, 3, c2_2_tax_4, format4)
                sheet2.write(row, 4, c2_2_tax_8, format4)
                sheet2.write(row, 5, c2_2_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Bienes de Capital-Local', format5)
                sheet2.write(row, column + 1, c2_3, negrita_numero)
                sheet2.write(row, 2, c2_3_tax_1, format4)
                sheet2.write(row, 3, c2_3_tax_4, format4)
                sheet2.write(row, 4, c2_3_tax_8, format4)
                sheet2.write(row, 5, c2_3_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Gastos por servicios-Local', format5)
                sheet2.write(row, column + 1, c2_4, negrita_numero)
                sheet2.write(row, 2, c2_4_tax_1, format4)
                sheet2.write(row, 3, c2_4_tax_4, format4)
                sheet2.write(row, 4, c2_4_tax_8, format4)
                sheet2.write(row, 5, c2_4_tax_13, format4)
                row +=2

                sheet2.write(row, column, 'IVA Soportado-EXTERIOR', format2)
                sheet2.write(row, column + 1, c3_1, negrita_numero_border)
                sheet2.write(row, 2, (c3_2_tax_1 + c3_3_tax_1 + c3_4_tax_1), negrita_numero_border)
                sheet2.write(row, 3, (c3_2_tax_4 + c3_3_tax_4 + c3_4_tax_4), negrita_numero_border)
                sheet2.write(row, 4, (c3_2_tax_8 + c3_3_tax_8 + c3_4_tax_8), negrita_numero_border)
                sheet2.write(row, 5, (c3_2_tax_13 + c3_3_tax_13 + c3_4_tax_13), negrita_numero_border)
                row +=1
                sheet2.write(row, column, 'Compra de bienes-Exterior', format5)
                sheet2.write(row, column + 1, c3_2, negrita_numero)
                sheet2.write(row, 2, c3_2_tax_1, format4)
                sheet2.write(row, 3, c3_2_tax_4, format4)
                sheet2.write(row, 4, c3_2_tax_8, format4)
                sheet2.write(row, 5, c3_2_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Bienes de Capital-Exterior', format5)
                sheet2.write(row, column + 1, c3_3, negrita_numero)
                sheet2.write(row, 2, c3_3_tax_1, format4)
                sheet2.write(row, 3, c3_3_tax_4, format4)
                sheet2.write(row, 4, c3_3_tax_8, format4)
                sheet2.write(row, 5, c3_3_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Gastos por servicios-Exterior', format5)
                sheet2.write(row, column + 1, c3_4, negrita_numero)
                sheet2.write(row, 2, c3_4_tax_1, format4)
                sheet2.write(row, 3, c3_4_tax_4, format4)
                sheet2.write(row, 4, c3_4_tax_8, format4)
                sheet2.write(row, 5, c3_4_tax_13, format4)
                row +=2

                sheet2.write(row, column, 'Compras con IVA soportado acreditable-EXTERIOR', format2)
                sheet2.write(row, column + 1, c4_1, negrita_numero_border)
                sheet2.write(row, 2, (c4_2_tax_1 + c4_3_tax_1 + c4_4_tax_1), negrita_numero_border)
                sheet2.write(row, 3, (c4_2_tax_4 + c4_3_tax_4 + c4_4_tax_4), negrita_numero_border)
                sheet2.write(row, 4, (c4_2_tax_8 + c4_3_tax_8 + c4_4_tax_8), negrita_numero_border)
                sheet2.write(row, 5, (c4_2_tax_13 + c4_3_tax_13 + c4_4_tax_13), negrita_numero_border)
                row +=1
                sheet2.write(row, column, 'Compra de bienes-Exterior', format5)
                sheet2.write(row, column + 1, c4_2, negrita_numero)
                sheet2.write(row, 2, c4_2_tax_1, format4)
                sheet2.write(row, 3, c4_2_tax_4, format4)
                sheet2.write(row, 4, c4_2_tax_8, format4)
                sheet2.write(row, 5, c4_2_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Bienes de Capital-Exterior', format5)
                sheet2.write(row, column + 1, c4_3, negrita_numero)
                sheet2.write(row, 2, c4_3_tax_1, format4)
                sheet2.write(row, 3, c4_3_tax_4, format4)
                sheet2.write(row, 4, c4_3_tax_8, format4)
                sheet2.write(row, 5, c4_3_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Gastos por servicios-Exterior', format5)
                sheet2.write(row, column + 1, c4_4, negrita_numero)
                sheet2.write(row, 2, c4_4_tax_1, format4)
                sheet2.write(row, 3, c4_4_tax_4, format4)
                sheet2.write(row, 4, c4_4_tax_8, format4)
                sheet2.write(row, 5, c4_4_tax_13, format4)
                row +=2

                sheet2.write(row, column, 'Compras sin IVA soportado y/o con IVA soportado no acreditable', format2)
                sheet2.write(row, 1, c5_1, negrita_numero_border)
                sheet2.write(row, 2, (c5_2_tax_1 + c5_3_tax_1 + c5_4_tax_1 + c5_5_tax_1), negrita_numero_border)
                sheet2.write(row, 3, (c5_2_tax_4 + c5_3_tax_4 + c5_4_tax_4 + c5_5_tax_4), negrita_numero_border)
                sheet2.write(row, 4, (c5_2_tax_8 + c5_3_tax_8 + c5_4_tax_8 + c5_5_tax_8), negrita_numero_border)
                sheet2.write(row, 5, (c5_2_tax_13 + c5_3_tax_13 + c5_4_tax_13 + c5_5_tax_13), negrita_numero_border)
                row +=1
                sheet2.write(row, column, 'Bienes y servicios locales (Exenciones)', format5)
                sheet2.write(row, column + 1, c5_2, negrita_numero)
                sheet2.write(row, 2, c5_2_tax_1, format4)
                sheet2.write(row, 3, c5_2_tax_4, format4)
                sheet2.write(row, 4, c5_2_tax_8, format4)
                sheet2.write(row, 5, c5_2_tax_13, format4)
                row +=1
                sheet2.write(row, column, 'Bienes y servicios exterior (Exenciones)', format5)
                sheet2.write(row, column + 1, c5_3, negrita_numero)
                sheet2.write(row, 2, c5_3_tax_1, format4)
                sheet2.write(row, 3, c5_3_tax_4, format4)
                sheet2.write(row, 4, c5_3_tax_8, format4)
                sheet2.write(row, 5, c5_3_tax_13, format4)

                row +=1
                sheet2.write(row, column, 'Bienes y servicios locales (No sujeción)', format5)
                sheet2.write(row, column + 1, c5_4, negrita_numero)
                sheet2.write(row, 2, c5_4_tax_1, format4)
                sheet2.write(row, 3, c5_4_tax_4, format4)
                sheet2.write(row, 4, c5_4_tax_8, format4)
                sheet2.write(row, 5, c5_4_tax_13, format4)

                row +=1
                sheet2.write(row, column, 'Bienes y servicios exterior (No sujeción)', format5)
                sheet2.write(row, column + 1, c5_5, negrita_numero)
                sheet2.write(row, 2, c5_5_tax_1, format4)
                sheet2.write(row, 3, c5_5_tax_4, format4)
                sheet2.write(row, 4, c5_5_tax_8, format4)
                sheet2.write(row, 5, c5_5_tax_13, format4)



                sheet2.hide_gridlines(2)

            

            workbook.close()
            output.seek(0)
            response.stream.write(output.read())
            output.close()

