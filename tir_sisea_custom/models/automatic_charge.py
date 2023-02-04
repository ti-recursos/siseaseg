from odoo import fields, models, api, tools, _
from odoo.exceptions import UserError
from cryptography.fernet import Fernet
import base64

import requests
import json
import datetime
import pytz
from time import strftime, gmtime

#Excel Data
import xlrd
import tempfile
import binascii
import dateutil.parser

import logging
_logger = logging.getLogger(__name__)


class AutomaticCharge(models.Model):
    _name = 'automatic.charge'
    _description = 'Automatic Charge'

    name = fields.Char(string="Name", required=False)

    name_file = fields.Char(string='Charge Document Name', readonly=True)
    file = fields.Binary(string="Charge Document", required=False, copy=False, attachment=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False)
    date_doc = fields.Date(string='Date', required=True, readonly=False)

    doc_quantity = fields.Integer(string='Total Documents')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=False)
    amount_total = fields.Monetary(string='Amount Total', required=True, readonly=False)

    state = fields.Selection(
        selection=[('0', 'NO ENVIADO'),
                   ('1', 'ENVIADO'),
                   ('2', 'EN PROCESO'),
                   ('3', 'ACEPTADO')
                   ],
        string="Internal State",
        required=False,
        help=""
    )


class AutomaticChargeLine(models.Model):
    _name = 'automatic.charge.line'
    _description = 'Automatic Charge Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=False)

    move_id = fields.Many2one('account.move', string="Invoice", required=False)
    payment_id = fields.Many2one('account.payment', string="Payment", required=False)
    card_id = fields.Many2one('res.partner.cards', string="Partner Card Information", required=False)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=False)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False)
    amount_total = fields.Monetary(string='Amount Total', required=True, readonly=False)
    date_doc = fields.Date(string='Date', required=True, readonly=False)

    send = fields.Boolean(string="Recurring Charges Send", default=False)

    bank_answer = fields.Char(string="Bank Answer", required=False)
    json_post = fields.Char(string="JSON", required=False)
    n_autorizacion = fields.Char(string="Authorization Number", required=False)
    observacion = fields.Char(string="Notes", required=False)

    partner_id = fields.Many2one('res.partner', string="Cliente de Factura", required=False, compute="_compute_partner")

    processed = fields.Boolean(string="Processed", default=False)

    payment_state = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('process', 'In Process'),
        ('no_auth', 'Unauthorized'),
        ('cancel', 'Cancelado'),
        ('paid', 'Paid')],
        string="Payment Status", store=True, readonly=True, copy=False, tracking=True)

    contract = fields.Many2one('sale.subscription', string="Suscripción", required=False)

    def write(self, vals):

        if 'move_id' in vals:
            odoobot_id = self.env['ir.model.data'].xmlid_to_res_id("base.partner_root")
            anterior = self.env['account.move'].sudo().search([('id', '=', self.move_id.id)])
            nueva = self.env['account.move'].sudo().search([('id', '=', vals['move_id'])])

            if self.payment_state == 'process':

                if anterior.amount_total != nueva.amount_total:
                    diferente = '<p>El cargo automático ya se envió al banco y el monto es distinto, por favor verifique el monto del documento o coloque otro documento</p>'
                    self.message_post(body=diferente, author_id=odoobot_id)
                else:
                    igual = _('<ul><li><p>Factura: ' + anterior.name + ' &#8594; ' + nueva.name + '</p></li></ul>')
                    self.message_post(body=igual, author_id=odoobot_id)
                    vals['name'] = nueva.name
                    result = super(AutomaticChargeLine, self).write(vals)
                    return result
            elif self.payment_state == 'not_paid':
                msg_body = _('<ul><li><p>Factura: ' + anterior.name + ' &#8594; ' + nueva.name + '</p></li><li><p>Monto: ' + str(anterior.amount_total) + ' &#8594; ' + str(nueva.amount_total) + '</p></li></ul>')
                self.message_post(body=msg_body)

                vals['amount_total'] = nueva.amount_total
                vals['name'] = nueva.name

                result = super(AutomaticChargeLine, self).write(vals)
                return result
            elif self.payment_state in ['no_auth', 'paid']:
                payment_no = _('No puede modificar el documento de un cargo automático que se encuentra ' + self.payment_state)
                self.message_post(body=payment_no, author_id=odoobot_id)
        else:
            result = super(AutomaticChargeLine, self).write(vals)
            return result

    def _compute_partner(self):
        for doc in self:
            if doc.move_id:
                doc.partner_id = doc.move_id.partner_id.id
            else:
                doc.partner_id = False

    def resend(self):
        current_date = datetime.date.today()
        res_id = self.copy({
            'date_doc': current_date,
            'name': _('RESEND: ') + self.name,
            'processed': False,
            'send':False,
            'payment_state': 'not_paid',
            'bank_answer': False,
            'n_autorizacion': False,
                   })
        return {
            'name': _('Modify Asset'),
            'view_mode': 'form',
            'res_model': 'automatic.charge.line',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': res_id.id,
            'context': self.env.context,
        }

    # -------------------------------------------------------------------------
    # NEW CODE
    # -------------------------------------------------------------------------
    # 29/01/2023
    # Este código se encargará de crear el pago del documento
    #
    # -------------------------------------------------------------------------

    def send_manual_laro_recurring_charges(self):
        string = ""
        contador = 1
        total_cobros = len(self)
        amount_total = 0

        _logger.info("LARO MANUAL: Documentos por enviar %s" % total_cobros)

        for charge in self:
            key = charge.company_id.tir_key
            _logger.info("LARO MANUAL: Iniciando proceso %s de %s: Cargo: %s" % (contador, total_cobros, charge.name))

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
                if charge.move_id.currency_id.id != charge.company_id.currency_id.id:
                    convert_amount = charge.move_id.currency_id._convert(
                        charge.move_id.amount_residual,
                        charge.company_id.company_id.currency_id,
                        charge.company_id,
                        charge.move_id.date
                    )
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
                    # total_str = str(total).zfill(10)
                    # if contador == len(recurring_charges):
                    #     string += (card_n + total_str + nro_afilidado + send_date + date_due.replace('/', '') + comment + date_cr)
                    # else:
                    #     string += (card_n + total_str + nro_afilidado + send_date + date_due.replace('/', '') + comment + date_cr + "\r\n")

                    url_laro = charge.company_id.url_laro_automatic_charge

                    if url_laro[-1:] == '/':
                        url_laro = url_laro[:-1]

                    token = charge.company_id.token_laro
                    id_laro = charge.company_id.id_laro
                    idTransaccion = 1
                    fechaVencimiento = date_due.replace('/', '')
                    email = charge.move_id.partner_id.email
                    identificadorUnico = charge.id
                    monto = charge.amount_total

                    data = {
                        "idUsuario": str(id_laro),
                        "token":  str(token),
                        "idTransaccion": idTransaccion,
                        "tarjeta":  str(card_n),
                        "fechaVencimiento": str(fechaVencimiento),
                        "monto": monto,
                        "identificadorUnico": str(identificadorUnico),
                        "email": str(email)
                    }
                    json_str = str(data)
                    charge.json_post = json_str
                    _logger.info("LARO MANUAL: Información a enviar: %s" % json_str)

                    res_post = requests.post(url_laro, json=data)

                    respuesta_dict = json.loads(res_post.text)
                    if respuesta_dict.get("codigoRespuesta") == "00":
                        charge._process_payment(respuesta_dict)
                    else:
                        charge.n_autorizacion = respuesta_dict.get('autorizacion')
                        charge.observacion = str(respuesta_dict)

                        charge.processed = True
                        charge.payment_state = 'no_auth'

                    charge.send = True

                    contador += 1

                else:
                    _logger.warning(_("Documento: #" + charge.name + " no se pudo aplicar el cargo automático"))
            else:
                charge.send = True
                charge.payment_state = 'cancel'
                contador += 1
            total = 0

    def _process_payment(self, datos):
        '''
            En Odoo 14 no se utiliza account.payment para guardar un pago,
            sino que se debe realiza desde account.payment.register
        '''
        self.ensure_one()
        cargo = self
        journal_id = self.env.ref('tir_api_cisa.journal_bank_151').id

        if cargo.move_id.payment_state == 'no_paid':
            cargo.n_autorizacion = datos.get('autorizacion')
            cargo.observacion = str(datos)

            payment_id = self.env['account.payment.register'].sudo().with_context(
                active_model='account.move',
                active_ids=cargo.move_id.ids
            ).create(
                {
                    'payment_date': cargo.date_doc,
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                    'amount': cargo.amount_total,
                    'currency_id': cargo.currency_id.id,
                    'journal_id': journal_id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': cargo.move_id.partner_id.id,
                }
            )

            pago = payment_id.action_create_payments()
            payment = self.env['account.payment'].sudo().search(
                [
                    ('id', '=', pago['res_id'])
                ],
                limit=1
            )

            # Publicación del Pago
            if payment.state == 'draft':
                payment.payment_method = 'automatic_charge'
                if cargo.contract:
                    payment.contract = cargo.contract.code
                payment.action_post()
            if cargo.contract:
                payment.contract = cargo.contract.code
            payment.payment_method = 'automatic_charge'
            payment.ref = cargo.n_autorizacion

            cargo.move_id.payment_id = payment.id
            cargo.payment_id = payment.id
            cargo.payment_state = 'paid'
        else:
            cargo.n_autorizacion = datos.get('autorizacion')
            cargo.observacion = str(datos)

            payment_id = self.env['account.payment.register'].sudo().with_context(
                active_model='account.move',
                active_ids=cargo.move_id.ids
            ).create(
                {
                    'payment_date': cargo.date_doc,
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                    'amount': cargo.amount_total,
                    'currency_id': cargo.currency_id.id,
                    'journal_id': journal_id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': cargo.move_id.partner_id.id,
                }
            )

            pago = payment_id.action_create_payments()
            payment = self.env['account.payment'].sudo().search(
                [
                    ('id', '=', pago['res_id'])
                ],
                limit=1
            )

            # Publicación del pago
            if payment.state == 'draft':
                payment.payment_method = 'automatic_charge'
                if cargo.contract:
                    payment.contract = cargo.contract.code
                payment.action_post()
            if cargo.contract:
                payment.contract = cargo.contract.code
            payment.payment_method = 'automatic_charge'
            payment.ref = cargo.n_autorizacion

            cargo.payment_id = payment.id
            cargo.payment_state = 'paid'

        cargo.processed = True


class AutomaticChargeBank(models.Model):
    _name = 'automatic.charge.bank'
    _description = 'Automatic Charge Receptor'

    name = fields.Char(string="Name", required=False)

    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False)
    date_doc = fields.Date(string='Date', required=True, readonly=False)

    bank_charge_ids = fields.One2many(
        'automatic.charge.bank.line',
        'bank_charge_id',
        string='Bank Answer Files'
    )

    # TODO leer archivos que envió el banco
    def read_lines(self):
        for bank_charge in self.bank_charge_ids:
            if '.xlsx' in bank_charge.name:
                if 'CONV' in bank_charge.name:
                    self.read_excel(bank_charge.file_data)


    def process_line(self, datos):
        if self.company_id.nr_afiliado == datos['afiliado']:
            _logger.info('Cargo por procesar %s', datos)
            date_time_str = datos['f_compra']
            date_time_obj = datetime.datetime.strptime(date_time_str, '%d/%m/%Y')
            cargos = self.env['automatic.charge.line'].search([('date_doc', '=', date_time_obj), ('amount_total', '=', float(datos['monto'])), ('send', '=', True), ('processed', '=', False), ('payment_state', '=', 'process')])

            _logger.info('Cargo encontrados %s', str(len(cargos)))

            for cargo in cargos:
                key = self.company_id.tir_key
                a = str(cargo.card_id.n_card).encode('ascii', errors='ignore').decode()

                dato = cargo.card_id._decrypt(bytes(a, 'utf-8'), key)

                if int(dato) == int(datos['tarjeta']):
                    cargo.bank_answer = datos['respuesta']

                    if '00-APROBADO' in cargo.bank_answer:
                        '''
                            En Odoo 14 no se utiliza account.payment para guardar un pago,
                            sino que se debe realiza desde account.payment.register
                        '''
                        journal_id = self.env.ref('tir_api_cisa.journal_bank_151').id

                        if cargo.move_id.payment_state == 'no_paid':
                            cargo.n_autorizacion = datos['autorizacion']
                            cargo.observacion = datos['info_adicional']

                            payment_id = self.env['account.payment.register'].sudo().with_context(
                                active_model='account.move', active_ids=cargo.move_id.ids).create({
                                'payment_date': cargo.date_doc,
                                'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                                'amount': cargo.amount_total,
                                'currency_id': cargo.currency_id.id,
                                'journal_id': journal_id,
                                'payment_type': 'inbound',
                                'partner_type': 'customer',
                                'partner_id': cargo.move_id.partner_id.id,
                            })

                            pago = payment_id.action_create_payments()
                            payment = self.env['account.payment'].sudo().search([('id', '=', pago['res_id'])], limit=1)
                            # Publicación del Pago
                            if payment.state == 'draft':
                                payment.payment_method = 'automatic_charge'
                                if cargo.contract:
                                    payment.contract = cargo.contract.code
                                payment.action_post()
                            if cargo.contract:
                                payment.contract = cargo.contract.code
                            payment.payment_method = 'automatic_charge'
                            payment.ref = cargo.n_autorizacion

                            cargo.move_id.payment_id = payment.id
                            cargo.payment_id = payment.id
                            cargo.payment_state = 'paid'
                        else:
                            cargo.n_autorizacion = datos['autorizacion']
                            cargo.observacion = datos['info_adicional']

                            payment_id = self.env['account.payment.register'].sudo().with_context(
                                active_model='account.move', active_ids=cargo.move_id.ids).create({
                                'payment_date': cargo.date_doc,
                                'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                                'amount': cargo.amount_total,
                                'currency_id': cargo.currency_id.id,
                                'journal_id': journal_id,
                                'payment_type': 'inbound',
                                'partner_type': 'customer',
                                'partner_id': cargo.move_id.partner_id.id,
                            })

                            pago = payment_id.action_create_payments()
                            payment = self.env['account.payment'].sudo().search([('id', '=', pago['res_id'])], limit=1)
                            # Publicación del pago
                            if payment.state == 'draft':
                                payment.payment_method = 'automatic_charge'
                                if cargo.contract:
                                    payment.contract = cargo.contract.code
                                payment.action_post()
                            if cargo.contract:
                                payment.contract = cargo.contract.code
                            payment.payment_method = 'automatic_charge'
                            payment.ref = cargo.n_autorizacion

                            cargo.payment_id = payment.id
                            cargo.payment_state = 'paid'

                        cargo.processed = True
                        break
                    else:
                        cargo.n_autorizacion = datos['autorizacion']
                        cargo.observacion = datos['info_adicional']

                        cargo.processed = True
                        cargo.payment_state = 'no_auth'
                        break

    def read_excel(self, Documento):
        try:
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            fp.write(binascii.a2b_base64(Documento))
            fp.seek(0)
            workbook = xlrd.open_workbook(fp.name)
            sheet = workbook.sheet_by_index(0)

            rows = sheet.get_rows()
            n_row = 0

            for row in rows:
                n_column = 0
                if n_row > 0:
                    Info = {}
                    for column in row:
                        # Saltamos el Encabezado
                        if n_row > 0:
                            if n_column == 0:
                                if len(str(column.value)) > 0:
                                    tarjeta = str(column.value)
                                    Info['tarjeta'] = tarjeta
                            if n_column == 1:
                                if len(str(column.value)) > 0:
                                    afiliado = str(column.value)
                                    Info['afiliado'] = afiliado
                            if n_column == 2:
                                if len(str(column.value)) > 0:
                                    nombre = str(column.value)
                                    Info['nombre'] = nombre
                            if n_column == 3:
                                if len(str(column.value)) > 0:
                                    f_compra = str(column.value)
                                    Info['f_compra'] = f_compra
                            if n_column == 4:
                                if len(str(column.value)) > 0:
                                    f_proceso = str(column.value)
                                    Info['f_proceso'] = f_proceso
                            if n_column == 5:
                                if len(str(column.value)) > 0:
                                    respuesta = str(column.value)
                                    Info['respuesta'] = respuesta
                            if n_column == 6:
                                if len(str(column.value)) > 0:
                                    autorizacion = str(column.value)
                                    Info['autorizacion'] = autorizacion
                            if n_column == 7:
                                if len(str(column.value)) > 0:
                                    moneda = str(column.value)
                                    Info['moneda'] = moneda
                            if n_column == 8:
                                if len(str(column.value)) > 0:
                                    monto = str(column.value)
                                    Info['monto'] = monto
                            if n_column == 9:
                                if len(str(column.value)) > 0:
                                    info_adicional = str(column.value)
                                    Info['info_adicional'] = info_adicional
                                else:
                                    Info['info_adicional'] = ''
                        n_column += 1
                    self.process_line(Info)
                    #print(Info)
                n_row += 1

        except Exception as e:
            raise UserError(('Ocurrió un error al leer el archivo, fila: ' + str(n_row) +' columns: ' + str(n_column) + ', Excepción %s ' ) % e)

    def read_paywait(self, Documento):
        print('Procesando')


class AutomaticChargeBankLine(models.Model):
    _name = 'automatic.charge.bank.line'
    _description = 'Automatic Charge Receptor Line'

    name = fields.Char(string="Name", required=False)
    file_data = fields.Binary(string="Archivo", required=False, copy=False, attachment=True)

    bank_charge_id = fields.Many2one(
        comodel_name='automatic.charge.bank',
        string='Bank Answer'
    )