# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.date_utils import get_month, get_fiscal_year
from odoo.tools.misc import format_date

import datetime
import pytz

import re
from collections import defaultdict
import json
import tempfile
import base64
import logging

_logger = logging.getLogger(__name__)

class DateWizard(models.TransientModel):
    _name = 'automatic.charge.line.change'
    _description = 'Change Date Automatic Charges'

    date = fields.Date(string="Fecha Nueva")
    process = fields.Boolean(string="¿Incluir los cargos que están en proceso?", default=False, help="Cambiar Fecha inclusive a los documentos que ya fueron enviados al banco (esto sirve por si el banco procesó los cargos otro día)")


    def resequence(self):

        now_utc = datetime.datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        hoy = now_cr.strftime("%d/%m/%Y")

        nueva = self.date.strftime("%d/%m/%Y")
        if self.process == True:
            lineas = self.env['automatic.charge.line'].sudo().search([('id', 'in', self.env.context['active_ids']), ('payment_state', 'in', ['not_paid', 'process'])])
        else:
            lineas = self.env['automatic.charge.line'].sudo().search([('id', 'in', self.env.context['active_ids']), ('payment_state', '=', 'not_paid')])

        if lineas:
            for linea in lineas:
                de = linea.date_doc.strftime("%d/%m/%Y")
                body = _('Se cambió la fecha de ' + de + ' a ' + nueva + ' Estado del Cargo: ' + linea.payment_state)
                linea.date_doc = self.date
                linea.message_post(body=body)

    def regenerate_file(self):
        try:
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            fp.seek(0)

            current_date = datetime.date.today()
            nueva = self.date.strftime("%d/%m/%Y")

            now_utc = datetime.datetime.now(pytz.timezone('UTC'))
            now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
            date_cr = self.date.strftime("%Y%m%d")
            send_date = self.date.strftime("%d%m%Y")
            if self.process == True:
                recurring_charges = self.env['automatic.charge.line'].sudo().search([('id', 'in', self.env.context['active_ids']), ('payment_state', 'in', ['not_paid', 'process'])])
            else:
                recurring_charges = self.env['automatic.charge.line'].sudo().search([('id', 'in', self.env.context['active_ids']), ('payment_state', '=', 'not_paid')])
            key = self.env.user.company_id.tir_key
            string = ""
            contador = 0
            amount_total = 0
            if len(recurring_charges) > 0:
                for charge in recurring_charges:

                    nro = str(charge.card_id.n_card).encode('ascii', errors='ignore').decode()
                    vcm = str(charge.card_id.date_due).encode('ascii', errors='ignore').decode()
                    nro_afilidado = charge.company_id.nr_afiliado

                    card_n = charge.card_id._decrypt(bytes(nro, 'utf-8'), key).decode()
                    date_due = charge.card_id._decrypt(bytes(vcm, 'utf-8'), key).decode()
                    if charge.contract:
                        comment = "Contrato: " + str(charge.contract.code) + " "
                    else:
                        comment = "Factura: " + str(charge.move_id.name) + " "

                    # Re calculo el monto en caso de que el documento esté pagado "parcialmente"
                    if charge.move_id.payment_state == "partial":
                        if charge.move_id.company_id.currency_id.id != charge.company_id.currency_id.id:
                            convert_amount = charge.move_id.currency_id._convert(charge.move_id.amount_residual, charge.company_id.company_id.currency_id, charge.company_id, charge.move_id.date)
                            charge.amount_total = convert_amount
                        else:
                            convert_amount = charge.move_id.amount_residual
                            charge.amount_total = convert_amount
                    else:
                        convert_amount = charge.amount_total

                    if charge.move_id.payment_state not in ("paid", "reversed"):
                        total = "{:.2f}".format(convert_amount)
                        amount_total += convert_amount

                        if not False in [nro, vcm, nro_afilidado, card_n, date_due, comment, total]:
                            #f = open(fp.name, "w")
                            total_str = str(total).zfill(10)
                            if contador == len(recurring_charges):
                                string += (card_n + total_str + nro_afilidado + send_date + date_due.replace('/', '') + comment + date_cr)
                            else:
                                string += (card_n + total_str + nro_afilidado + send_date + date_due.replace('/', '') + comment + date_cr + "\r\n")
                            charge.send = True
                            charge.payment_state = 'process'
                            contador += 1
                            
                            de = charge.date_doc.strftime("%d/%m/%Y")
                            body = _('Se cambió la fecha de ' + de + ' a ' + nueva + ' Estado del Cargo: ' + charge.payment_state)
                            charge.date_doc = self.date
                            charge.message_post(body=body)


                        else:
                            _logger.warning(_("Documento: #" + charge.name + " no se pudo aplicar el cargo automático"))
                    else:
                        charge.send = True
                        charge.payment_state = 'cancel'
                        contador += 1
                    total = 0
                try:

                    charge_data = self.env['automatic.charge'].sudo().create({
                        'name': 'WCF' + nro_afilidado + ' ' + now_cr.strftime("%d/%m/%Y %H:%M:%S"),
                        'name_file': nro_afilidado + '.txt',
                        'file': base64.encodebytes(string.encode('utf')),
                        'state': '0',
                        'company_id': self.env.user.company_id.id,
                        'date_doc': current_date,
                        'doc_quantity': contador,
                        'currency_id': self.env.user.company_id.currency_id.id,
                        'amount_total': amount_total,
                    })

                    self.env['ir.attachment'].sudo().create({
                        'name': charge_data.name_file,
                        'type': 'binary',
                        'datas': charge_data.file,
                        'res_model': 'automatic.charge',
                        'mimetype': 'text/xml',
                        'res_id': charge_data.id
                    })
                    # f.close()

                except Exception as e:
                    raise UserError(_('Ocurrió un error al crear el archivo a enviar'))

        except Exception as e:
            raise UserError(_('Ocurrió un error al crear el archivo temporal'))
