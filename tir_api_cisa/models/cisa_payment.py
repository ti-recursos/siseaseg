# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import datetime
import pytz

#Read Txt
import tempfile
import binascii

import logging
_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _name = "cisa.payment"
    _description = "Importar datos de Banco"

    name = fields.Char(string='Nombre')
    date_import = fields.Datetime(string='Fecha de Importación')
    file_data = fields.Binary(string="Archivo", required=False, copy=False, attachment=True)
    preview_html = fields.Html(string="Vista Previa", readonly=False)
    state = fields.Boolean(string="Estado de Importación", required=False, default=False)
    cisa_payment_line_ids = fields.One2many(
        'cisa.payment.line',
        'cisa_payment_id',
        string='Pagos Documento'
    )


    def compararDocumento(self, Documento, Resumen):
        html_text = '<div style="width: 100%; height: 400px; overflow-y: scroll;" class="row"><table class="table">'
        html_text += '<tr style="line-height: 12px; height: 12px; width: auto; margin-left: auto;margin-right: auto;">'

        # Datos de Banco
        html_text += '<th style="position: sticky; top: 0;background-color:#875A7B; color: white">Número Factura</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#875A7B; color: white">Fecha del pago</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#875A7B; color: white">Moneda</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#875A7B; color: white">Impuesto</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#875A7B; color: white">Pago</th>'


        html_text += '<th style="position: sticky; top: 0;background-color:#00A09D; color: white">Fecha del Documento</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#00A09D; color: white">Moneda</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#00A09D; color: white">Impuesto Doc.</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#00A09D; color: white">Total Doc.</th>'
        html_text += '<th style="position: sticky; top: 0;background-color:#00A09D; color: white">Estado</th>'

        html_text += '</tr>'

        for Doc in Documento:
            html_text += '<tr>'

            # Datos de Banco
            html_text += '<td style="line-height: 12px;">' + str(Doc['move_id']) + '</td>'
            html_text += '<td style="line-height: 12px;">' + str(Doc['fecha_pago'].strftime("%d/%m/%Y")) + '</td>'
            # Moneda
            if str(Doc['cod_moneda']) == '001':
                html_text += '<td style="line-height: 12px;">CRC</td>'
            elif str(Doc['cod_moneda']) == '002':
                html_text += '<td style="line-height: 12px;">USD</td>'
            else:
                html_text += '<td style="line-height: 12px;">EUR</td>'

            html_text += '<td style="line-height: 12px;" class="text-right">' + str(Doc['monto_impuesto']) + '</td>'
            html_text += '<td style="line-height: 12px;" class="text-right">' + str(Doc['monto_pago']) + '</td>'

            factura_int = int(str(Doc['move_id']))
            if len(str(factura_int)) < 11:
                Factura = self.env['account.move'].sudo().search([('id', '=', factura_int)])
            else:
                Factura = self.env['account.move'].sudo().search([('name', '=', factura_int), ('move_type', '=', 'out_invoice')], limit=1)

            if Factura:

                html_text += '<td style="line-height: 12px;">' + str(Factura.date.strftime("%d/%m/%Y")) + '</td>'
                # Moneda
                html_text += '<td style="line-height: 12px;">' + str(Factura.currency_id.name) + '</td>'
                html_text += '<td style="line-height: 12px;" class="text-right">' + str(Factura.amount_tax_signed) + '</td>'
                if str(Factura.amount_total_signed) != str(Doc['monto_pago']):
                    html_text += '<td style="line-height: 12px;" class="text-danger font-weight-bold text-right">' + str(Factura.amount_total_signed) + '</td>'
                else:
                    html_text += '<td style="line-height: 12px;" class="text-success font-weight-bold text-right">' + str(Factura.amount_total_signed) + '</td>'

                if str(Factura.payment_state) == 'paid' or str(Factura.payment_state) == 'in_payment':
                    html_text += '<td style="line-height: 12px;"><div class="alert alert-success rounded-pill text-center font-weight-bold shadow-sm" role="alert">Pagado</div></td>'
                else:
                    html_text += '<td style="line-height: 12px;"><div class="alert alert-danger rounded-pill text-center font-weight-bold shadow-sm" role="alert">No Pagado</div></td>'
            else:
                html_text += '<td style="line-height: 12px;">-</td>'
                html_text += '<td style="line-height: 12px;">-</td>'
                html_text += '<td style="line-height: 12px;">-</td>'
                html_text += '<td style="line-height: 12px;">-</td>'
                html_text += '<td style="line-height: 12px;">-</td>'
            html_text += '</tr>'

        Debito = 0
        Credito = 0

        for Doc in Resumen:
            if str(Doc['tipo_registro']) == '02':
                Debito += int(Doc['monto_nota']) / 100
            else:
                Credito += int(Doc['monto_nota']) / 100

        html_text += '<tr>'

        # Datos de Resumen Banco
        html_text += '<td style="line-height: 12px;"> </td>'
        html_text += '<td style="line-height: 12px;"><strong>Débito:</strong></td>'
        html_text += '<td style="line-height: 12px;" class="text-right"><i>' + str(Debito) + '</i></td>'
        html_text += '<td style="line-height: 12px;"><strong>Crédito:</strong></td>'
        html_text += '<td style="line-height: 12px;" class="text-right"><i>' + str(Credito) + '</i></td>'

        html_text += '</tr>'
        html_text += '</table></div>'

        return html_text

    def importar(self):
        if self.file_data:
            try:
                _logger.error('CISA Payment.importar - Creando archivo')
                fp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
                fp.write(binascii.a2b_base64(self.file_data))
                fp.seek(0)

                Documentos = []
                Resumen = []
                _logger.error('CISA Payment.importar - Abriendo archivo')
                with open(fp.name) as f:
                    lines = f.readlines()
                    n_linea = 1
                    _logger.error('CISA Payment.importar - Iniciando recorrido de lineas')
                    for line in lines:
                        if n_linea <= (len(lines) - 2):

                            Datos = {
                                'cisa_payment_id': self.id,
                                'tipo_registro': str(line[0:2]),
                                'cod_empresa': str(line[2:5]),
                                'cod_convenio': str(line[5:8]),
                                'cod_banco': str(line[8:12]),
                                'cod_agencia': str(line[12:16]),
                                'move_id': int(str(line[16:36])),
                                'verificacion': str(line[36:37]),
                                'cod_moneda': str(line[37:40]),
                                'access_key': str(line[40:70]),
                                'periodo': str(line[70:78]),
                                'fecha_pago': datetime.datetime(int(str(line[78:82])), int(str(line[82:84])), int(str(line[84:86]))),
                                'monto_impuesto': int(str(line[86:101])) / 100,
                                'monto_pago': int(str(line[101:116])) / 100,
                                'monto_comision': int(str(line[116:129])) / 100,
                                'cod_banco_emisor': str(line[129:133]),
                                'n_cuenta_banco_emisor': str(line[133:152]),
                                'n_cuenta_cheque_otro_banco': str(line[152:166]),
                                'partner_name': str(line[166:216]),
                                'n_comprobante': str(line[216:286])
                            }

                            Documentos.insert(len(Documentos), Datos)
                            _logger.error('CISA Payment.importar - Creando lineas cisa.payment.line')
                            self.env['cisa.payment.line'].sudo().create(Datos)
                            _logger.error('CISA Payment.importar - Lineas creadas cisa.payment.line')
                            n_linea += 1
                        else:
                            Datos = {
                                'tipo_registro': str(line[0:2]),
                                'cod_empresa': str(line[2:5]),
                                'cod_convenio': str(line[5:8]),
                                'cod_banco': str(line[8:12]),
                                'n_cuenta': str(line[12:42]),
                                'n_nota': str(line[42:52]),
                                'monto_nota': str(line[52:72]),
                                'cantidad_pagos': str(line[72:78])
                            }

                            Resumen.insert(len(Resumen), Datos)

                            n_linea += 1
                _logger.error('CISA Payment.importar - Iniciando dibujado de HTML')
                html = self.compararDocumento(Documentos, Resumen)
                self.preview_html = html
                self.date_import = datetime.datetime.now()
                self.state = True

            except Exception as e:
                raise UserError(_("Ocurrió un error al importar el archivo, error: %s") % e)



class AccountPaymentLine(models.Model):
    _name = "cisa.payment.line"
    _description = "CISA Payment Line"

    cisa_payment_id = fields.Many2one(
        comodel_name='cisa.payment',
        string='Pago Dato Banco'
    )
    tipo_registro = fields.Char(string='Tipo de registro')
    cod_empresa = fields.Char(string='Código de empresa')
    cod_convenio = fields.Char(string='Código de convenio')
    cod_banco = fields.Char(string='Código de Banco')
    cod_agencia = fields.Char(string='Código de Agencia')
    move_id = fields.Char(string='Número Factura')
    verificacion = fields.Char(string='Self de verificación')
    cod_moneda = fields.Char(string='Código de Moneda')
    access_key = fields.Char(string='Llave de acceso')
    periodo = fields.Char(string='Periodo del recibo')
    fecha_pago = fields.Date(string='Fecha del pago')
    monto_impuesto = fields.Float(string='Monto impuesto')
    monto_pago = fields.Float(string='Monto del pago')
    monto_comision = fields.Float(string='Monto de la comisión')
    cod_banco_emisor = fields.Char(string='Código Banco emisor cheque de otro banco')
    n_cuenta_banco_emisor = fields.Char(string='Número de cuenta cheque de otro banco')
    n_cuenta_cheque_otro_banco = fields.Char(string='Número de cheque otro banco')
    partner_name = fields.Char(string='Nombre del cliente')
    n_comprobante = fields.Char(string='Numero Comprobante')