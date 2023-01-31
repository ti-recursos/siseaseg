import logging
import requests
import json
import datetime
from typing_extensions import Self
import pytz
import traceback

from ast import literal_eval
from collections import Counter
from dateutil.relativedelta import relativedelta
from uuid import uuid4

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import format_date, float_compare
from odoo.tools.float_utils import float_is_zero
from odoo.tools.misc import get_lang


_logger = logging.getLogger(__name__)


import xlrd
import tempfile
import binascii
import base64
import calendar
import os


class SaleSubscriptionSISEA(models.Model):
    _inherit = 'sale.subscription'
    _description = "Sale Subscription"

    recurring_charges = fields.Boolean(string="Requiere Cargos Automáticos", default=False)
    charges_date_doc = fields.Date(string='Automatic Charges Date', required=False, readonly=False)

    credit_card = fields.Many2one('res.partner.cards', string="Credit Card")

    """
    Nuevos requerimientos, 5/8/2022 por Leandro
    Se solicitan 2 campos nuevos en el módulo de suscripciones.
        Gestor (Usuario de odoo encargado) Many2one
        Condición (Alto riesgo o normal) Select
    """

    @api.depends('has_subscription_perm')
    @api.onchange('has_subscription_perm')
    def _compute_has_permission(self):
        for record in self:
            record.has_subscription_perm = self.user_has_groups('tir_sisea_custom.subscription_category')

    has_subscription_perm = fields.Boolean('#Permiso',compute='_compute_has_permission')

    colaborator_gestor = fields.Many2one('res.users', string='manager')

    costumer_condition = fields.Selection([('highrisk', 'High Risk Costumer'),('normal','Normal Costumer'),('dxx2','DX X2'),('dxmoroso','DX Moroso')], string="Client condition")

    '''
        Dirección para tickets
    '''

    partner_direction = fields.Text(string="Dirección", required=False)

    '''
        Conteo de Tickets
    '''

    ticket_count = fields.Integer("Tickets", compute='_compute_ticket_count')


    '''
        Replicando comentarios de CRM
    '''
    has_comments = fields.Boolean(string="Posee Comentarios", compute='_compute_comments')
    
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



    '''
    CAMPOS NUEVOS
    
    '''
    img_placa = fields.Binary(string="Foto Frente y Placa", required=False, copy=False, attachment=True)
    img_placa_name = fields.Char(string="Nombre Foto", required=False)
    contract_latitude = fields.Float(string="Latitud", digits=(3,8) )
    contract_longitude = fields.Float(string="Longitud", digits=(3,8))
    gmaps = fields.Char(string="Punto Google Maps", required=False)
    resp_armada = fields.Char(string="Respuesta armada", required=False)
    cuen_SIS = fields.Char(string="Cuenta SIS", required=False)
    contract_base = fields.Char(string="Contrato Base", required=False)
    n_usuarios = fields.Char(string="# Usuarios")
    n_contactos = fields.Char(string="# Contactos")
    p_claves = fields.Char(string="Palabras Claves", required=False)
    n_temp = fields.Text(string="Notas Temporales", required=False)
    auto_beep_mail = fields.Char(string="Auto Beeper / Correo", required=False)
    senna_recurrente = fields.Char(string="Señales recurrentes", required=False)
    kit_alarma = fields.Char(string="Kit Alarmas", required=False)
    telecom_number = fields.Char(string="Telcom numero", required=False)
    app_serial = fields.Char(string="App Sisea Serial", required=False)
    app_sim = fields.Char(string="App Sisea SIM", required=False)
    gsm_number = fields.Char(string="GSM numero", required=False)
    recarga = fields.Char(string="Recarga", required=False)

    proveedor_sim = fields.Char(string="Proveedor", required=False)
    tipo_panel = fields.Char(string="Tipo Panel", required=False)
    ubica_panel = fields.Text(string="Ubicación Panel", required=False)
    tipo_teclado = fields.Char(string="Tipo Teclado", required=False)
    ubica_teclado = fields.Text(string="Ubicación Teclado", required=False)
    ubica_sirena = fields.Text(string="Ubicación Sirena", required=False)
    llaves_rf = fields.Char(string="Llaves RF")
    descrip_zonas = fields.Text(string="Descripcion de zonas", required=False)
    equipo_adicional = fields.Char(string="Equipos adicionales")
    aperturas_app = fields.Char(string="Aperturas, cierres, llaves, App Sisea", required=False)
    cierre_total_parcial = fields.Char(string="Cierres Total - Parcial", required=False)
    coaccion = fields.Char(string="Coacción", required=False)
    alarma_teclado = fields.Char(string="Alarmas Teclado Medical Incendio", required=False)
    panel_sabotaje = fields.Char(string="Sabotaje Panel", required=False)
    alarma_zonas = fields.Char(string="Alarmas Zonas", required=False)
    kit_cctv = fields.Char(string="Kit CCTV", required=False)
    dominio = fields.Char(string="Dominio", required=False)
    serie_dvr = fields.Text(string="DVR serial", required=False)
    ubica_dvr = fields.Text(string="Ubicación DVR", required=False)

    # Campos nuevos:

    f_contrato = fields.Date(string="Fecha del contrato", required=False)
    f_instalacion = fields.Date(string="Fecha de instalación", required=False)
    tecnico_instalador = fields.Char(string="Técnico instalador", required=False)
    enlace_compass = fields.Char(string="Enlace Compass")
    

    # Aquí irían los temas de las cámaras


    notas_tec = fields.Text(string="Notas Técnico", required=False)
    notas_opera = fields.Text(string="Notas Operador", required=False)


    camaras_ids = fields.One2many(
        'sale.subscription.camaras.line',
        'camara_id',
        string='Camaras',tracking=True
    )

    

    '''
    FINALIZAN CAMPOS NUEVOS
    '''

    number_ids = fields.One2many(
        'sale.subscription.number',
        'subscription_id',
        string='Subscription Numbers'
    )

    supp = fields.Boolean(string='Has Contacts', default=False)
    

    supp_ids = fields.One2many(
        'sale.subscription.soporte',
        'sub_id',
        string='Helpdesk Contacts'
    )

    pendiente_de_validar = fields.Boolean(default=False, tracking=True)


    _sql_constraints = [
        ('uniq_defaut_contract', 'unique(code)', "There is already a subscription with the indicated number!"),
    ]

    def action_create_contact(self):
        self.supp = True
        self.supp_ids = [(0, 0, {
            'sub_id': self.id,
            'secuencia': 0,
            'parent_id': self.partner_id.id
        })]

    def _compute_comments(self):
        for subscription in self:
            crm = self.env['crm.lead'].sudo().search([('contract', '=', subscription.code)], limit=1)
            if len(crm) > 0:
                subscription.com_calificado = crm.com_calificado or ''
                subscription.com_propuesta  = crm.com_propuesta or ''
                subscription.com_formalizacion  = crm.com_formalizacion or ''
                subscription.com_valida_doc  = crm.com_valida_doc or ''
                subscription.com_cuenta_monitoreo  = crm.com_cuenta_monitoreo or ''
                subscription.com_coordinacion  = crm.com_coordinacion or ''
                subscription.com_instalacion  = crm.com_instalacion or ''
                subscription.com_valida_cuenta  = crm.com_valida_cuenta or ''
                subscription.com_soporte  = crm.com_soporte or ''
                subscription.com_conta  = crm.com_conta or ''
                subscription.com_finalizado  = crm.com_finalizado or ''
                subscription.has_comments = True
            else:
                subscription.has_comments = False

    def _compute_ticket_count(self):
        # group tickets by partner, and account for each partner in self
        for ticket in self:
            tickets = self.env['helpdesk.ticket'].sudo().search([('partner_id', '=', ticket.partner_id.id), ('subscription_id', '=', ticket.id)],order='subscription_id asc')
            total = len(tickets)
            if total:
                ticket.ticket_count = total
            else:
                ticket.ticket_count = 0
            #self.ticket_count = total

    def action_open_helpdesk_ticket(self):
        action = self.env["ir.actions.actions"]._for_xml_id("helpdesk.helpdesk_ticket_action_main_tree")
        action['context'] = {}
        action['domain'] = [('partner_id', '=', self.partner_id.id), ('subscription_id', '=', self.id)]
        return action

    def name_get(self):
        res = []
        for sub in self.filtered('id'):
            partner_name = sub.partner_id.sudo().display_name
            subscription_name = '%s - %s' % (sub.code, partner_name) if sub.code else partner_name
            display_name = '%s' % (subscription_name)
            res.append((sub.id, display_name))
        return res

    @api.onchange('charges_date_doc')
    def charges_date_doc_changed(self):
        if self.recurring_next_date and self.charges_date_doc:
            if self.recurring_next_date > self.charges_date_doc:
                raise UserError(_("La fecha del próximo cargo automático debe ser igual o mayor a la fecha de la próxima factura"))

    def write(self, vals):
        res = super(SaleSubscriptionSISEA, self).write(vals)
        self.message_post(body="abc")
        return res

    # -------------------------------------------------------------------------
    # LEGACY CODE
    # -------------------------------------------------------------------------
    # 29/01/2023
    # Este código se encargaba de enviar el archivo al Banco Nacional.
    #
    # Se mantiene el código en caso de que en el futuro se requiera.
    # -------------------------------------------------------------------------

    def _try_send(self):
        charges = self.env['automatic.charge'].sudo().search([('state', '=', '0')])

        template = self.env.ref('tir_sisea_custom.email_bank_charge', raise_if_not_found=False)

        mail = self.env['ir.mail_server'].sudo().search([('active','=',True), ('type_bank','=',True)], limit=1)

        if len(mail) > 0:
            lang = False
            if not lang:
                lang = get_lang(self.env).code


            template.email_from = mail.smtp_user
            template.email_to = mail.bank_receiver

            if template:
                for charge in charges:
                    template.attachment_ids = [(5, 0, 0)]
                    template.subject = str(charge.company_id.nr_afiliado)
                    attachment = self.env['ir.attachment'].sudo().search([('res_model', '=', 'automatic.charge'), ('res_id', '=', charge.id)], limit=1)

                    template.attachment_ids = [(6, 0, [attachment.id])]

                    template.with_context(type='binary',
                                          default_type='binary').send_mail(res_id=charge.id, raise_exception=False,
                                                                           force_send=True)  # default_type='binary'

                    template.attachment_ids = [(5, 0, 0)]

                    charge.state = '1'

    # -------------------------------------------------------------------------
    # LEGACY CODE
    # -------------------------------------------------------------------------
    # 29/01/2023
    # Este código se encargaba de generar el archivo al Banco Nacional.
    #
    # Se mantiene el código en caso de que en el futuro se requiera.
    # -------------------------------------------------------------------------

    @api.model
    def _recurring_charges(self, automatic=False):
        try:
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            fp.seek(0)

            current_date = datetime.date.today()

            now_utc = datetime.datetime.now(pytz.timezone('UTC'))
            now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
            date_cr = now_cr.strftime("%Y%m%d")
            send_date = now_cr.strftime("%d%m%Y")
            domain = [('date_doc', '=', date_cr), ('send', '=', False)]
            recurring_charges = self.env['automatic.charge.line'].sudo().search(domain)
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


                        else:
                            _logger.warning(_("Documento: #" + charge.name + " no se pudo aplicar el cargo automático"))
                    else:
                        charge.send = True
                        charge.payment_state = 'cancel'
                        # contador += 1
                    total = 0
                try:

                    charge_data = self.env['automatic.charge'].sudo().create({
                        'name': nro_afilidado + ' ' + now_cr.strftime("%d/%m/%Y %H:%M:%S"),
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

                self._try_send()


        except Exception as e:
            raise UserError(_('Ocurrió un error al crear el archivo temporal'))

    # -------------------------------------------------------------------------
    # NEW CODE
    # -------------------------------------------------------------------------
    # 29/01/2023
    # Este código se encargará de enviar una petición POST a LARO SOLUTIONS
    # para aplicar un cargo automático.
    #
    # -------------------------------------------------------------------------

    @api.model
    def _laro_recurring_charges(self, automatic=False):
        current_date = datetime.date.today()

        now_utc = datetime.datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        date_cr = now_cr.strftime("%Y%m%d")
        send_date = now_cr.strftime("%d%m%Y")
        domain = [('date_doc', '=', date_cr), ('send', '=', False)]
        recurring_charges = self.env['automatic.charge.line'].sudo().search(domain)
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
                    # contador += 1
                total = 0

    @api.model
    def _cron_recurring_create_invoice(self):
        res = super(SaleSubscriptionSISEA, self)._cron_recurring_create_invoice()
        return res

    def add_months(self, sourcedate, months):
        month = sourcedate.month - 1 + months
        year = sourcedate.year + month // 12
        month = month % 12 + 1
        day = min(sourcedate.day, calendar.monthrange(year, month)[1])
        return datetime.date(year, month, day)

    def _recurring_create_invoice(self, automatic=False):
        auto_commit = self.env.context.get('auto_commit', True)
        cr = self.env.cr
        invoices = self.env['account.move']
        now_utc = datetime.datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        current_date = now_cr.date()
        imd_res = self.env['ir.model.data']
        template_res = self.env['mail.template']
        if len(self) > 0:
            subscriptions = self
        else:
            domain = [('recurring_next_date', '<=', current_date),
                      ('template_id.payment_mode', '!=', 'manual'),
                      '|', ('stage_category', '=', 'progress'), ('to_renew', '=', True)]
            subscriptions = self.search(domain)
        if subscriptions:
            sub_data = subscriptions.read(fields=['id', 'company_id'])
            for company_id in set(data['company_id'][0] for data in sub_data):
                sub_ids = [s['id'] for s in sub_data if s['company_id'][0] == company_id]
                subs = self.with_company(company_id).with_context(company_id=company_id).browse(sub_ids)
                Invoice = self.env['account.move'].with_context(move_type='out_invoice',
                                                                company_id=company_id).with_company(company_id)
                for subscription in subs:
                    subscription = subscription[
                        0]  # Trick to not prefetch other subscriptions, as the cache is currently invalidated at each iteration
                    if automatic and auto_commit:
                        cr.commit()

                    # if we reach the end date of the subscription then we close it and avoid to charge it
                    if automatic and subscription.date and subscription.date <= current_date:
                        subscription.set_close()
                        continue

                    # payment + invoice (only by cron)
                    if subscription.template_id.payment_mode in ['validate_send_payment',
                                                                 'success_payment'] and subscription.recurring_total and automatic:

                        if subscription.credit_card:
                            try:
                                invoice_values = subscription.with_context(
                                    lang=subscription.partner_id.lang)._prepare_invoice()
                                new_invoice = Invoice.create(invoice_values)
                                '''
                                    Esto se encarga de completar la información necesaria para que el documento pueda emitirse ante MH 
                                '''
                                company = self.env.user.company_id
                                if new_invoice.partner_id.payment_methods_id:
                                    new_invoice.payment_methods_id = new_invoice.partner_id.payment_methods_id.id
                                else:
                                    # El id = 5 equivale a Recaudado por tercero
                                    new_invoice.payment_methods_id = 5
                                new_invoice.economic_activity_id = company.activity_id.id

                                if subscription.analytic_account_id or subscription.tag_ids:
                                    for line in new_invoice.invoice_line_ids:
                                        if subscription.analytic_account_id:
                                            line.analytic_account_id = subscription.analytic_account_id
                                        if subscription.tag_ids:
                                            line.analytic_tag_ids = subscription.tag_ids

                                if new_invoice.company_id.currency_id.id != new_invoice.currency_id.id:
                                    convert_amount = new_invoice.currency_id._convert(new_invoice.amount_total,
                                                                                             new_invoice.company_id.currency_id,
                                                                                             new_invoice.company_id,
                                                                                             new_invoice.date)
                                else:
                                    convert_amount = new_invoice.amount_total


                                new_invoice.message_post_with_view(
                                    'mail.message_origin_link',
                                    values={'self': new_invoice, 'origin': subscription},
                                    subtype_id=self.env.ref('mail.mt_note').id)

                                invoices += new_invoice

                                if subscription.credit_card:
                                    subscription.validate_and_send_invoice(new_invoice)
                                    if new_invoice.state == 'posted':

                                        self.env['automatic.charge.line'].sudo().create({
                                            'name': new_invoice.name,
                                            'move_id': new_invoice.id,
                                            'card_id': subscription.credit_card.id,
                                            'currency_id': new_invoice.company_id.currency_id.id,
                                            'company_id': new_invoice.company_id.id,
                                            'contract': subscription.id,
                                            'amount_total': convert_amount,
                                            'date_doc': subscription.charges_date_doc,
                                            'payment_state': 'not_paid',
                                        })

                                    # Aumenta le periodo de la suscripcion y del cargo automático
                                    subscription.with_context(skip_update_recurring_invoice_day=True).increment_period()
                                    subscription.charges_date_doc = subscription.add_months(subscription.charges_date_doc, 1)

                                    if automatic:
                                        cr.commit()

                                else:
                                    if automatic:
                                        cr.rollback()

                            except ValueError as e:
                                _logger.warning(e)
                                if auto_commit:
                                    cr.rollback()


                        else:
                            try:
                                payment_token = subscription.payment_token_id
                                tx = None
                                if payment_token:
                                    invoice_values = subscription.with_context(lang=subscription.partner_id.lang)._prepare_invoice()
                                    new_invoice = Invoice.create(invoice_values)
                                    '''
                                        Esto se encarga de completar la información necesaria para que el documento pueda emitirse ante MH 
                                    '''
                                    company = self.env.user.company_id
                                    if new_invoice.partner_id.payment_methods_id:
                                        new_invoice.payment_methods_id = new_invoice.partner_id.payment_methods_id.id
                                    else:
                                        # El id = 5 equivale a Recaudado por tercero
                                        new_invoice.payment_methods_id = 5
                                    new_invoice.economic_activity_id = company.activity_id

                                    if subscription.analytic_account_id or subscription.tag_ids:
                                        for line in new_invoice.invoice_line_ids:
                                            if subscription.analytic_account_id:
                                                line.analytic_account_id = subscription.analytic_account_id
                                            if subscription.tag_ids:
                                                line.analytic_tag_ids = subscription.tag_ids
                                    new_invoice.message_post_with_view(
                                        'mail.message_origin_link',
                                        values={'self': new_invoice, 'origin': subscription},
                                        subtype_id=self.env.ref('mail.mt_note').id)
                                    tx = subscription._do_payment(payment_token, new_invoice, two_steps_sec=False)[0]
                                    # commit change as soon as we try the payment so we have a trace somewhere
                                    if auto_commit:
                                        cr.commit()
                                    if tx.renewal_allowed:
                                        msg_body = _(
                                            'Automatic payment succeeded. Payment reference: <a href=# data-oe-model=payment.transaction data-oe-id=%d>%s</a>; Amount: %s. Invoice <a href=# data-oe-model=account.move data-oe-id=%d>View Invoice</a>.') % (
                                                   tx.id, tx.reference, tx.amount, new_invoice.id)
                                        subscription.message_post(body=msg_body)
                                        if subscription.template_id.payment_mode == 'validate_send_payment':
                                            subscription.validate_and_send_invoice(new_invoice)
                                        else:
                                            # success_payment
                                            # Obtiene los datos del documento Electrónico
                                            new_invoice.action_post()
                                        subscription.send_success_mail(tx, new_invoice)
                                        if auto_commit:
                                            cr.commit()
                                    else:
                                        _logger.error('Fail to create recurring invoice for subscription %s',
                                                      subscription.code)
                                        if auto_commit:
                                            cr.rollback()
                                        new_invoice.unlink()
                                if tx is None or not tx.renewal_allowed:
                                    amount = subscription.recurring_total
                                    date_close = (
                                            subscription.recurring_next_date +
                                            relativedelta(days=subscription.template_id.auto_close_limit or
                                                               15)
                                    )
                                    close_subscription = current_date >= date_close
                                    email_context = self.env.context.copy()
                                    email_context.update({
                                        'payment_token': subscription.payment_token_id and subscription.payment_token_id.name,
                                        'renewed': False,
                                        'total_amount': amount,
                                        'email_to': subscription.partner_id.email,
                                        'code': subscription.code,
                                        'currency': subscription.pricelist_id.currency_id.name,
                                        'date_end': subscription.date,
                                        'date_close': date_close
                                    })
                                    if close_subscription:
                                        model, template_id = imd_res.get_object_reference('sale_subscription',
                                                                                          'email_payment_close')
                                        template = template_res.browse(template_id)
                                        template.with_context(email_context).send_mail(subscription.id)
                                        _logger.debug(
                                            "Sending Subscription Closure Mail to %s for subscription %s and closing subscription",
                                            subscription.partner_id.email, subscription.id)
                                        msg_body = _(
                                            'Automatic payment failed after multiple attempts. Subscription closed automatically.')
                                        subscription.message_post(body=msg_body)
                                        subscription.set_close()
                                    else:
                                        model, template_id = imd_res.get_object_reference('sale_subscription',
                                                                                          'email_payment_reminder')
                                        msg_body = _('Automatic payment failed. Subscription set to "To Renew".')
                                        if (datetime.date.today() - subscription.recurring_next_date).days in [0, 3, 7, 14]:
                                            template = template_res.browse(template_id)
                                            template.with_context(email_context).send_mail(subscription.id)
                                            _logger.debug(
                                                "Sending Payment Failure Mail to %s for subscription %s and setting subscription to pending",
                                                subscription.partner_id.email, subscription.id)
                                            msg_body += _(' E-mail sent to customer.')
                                        subscription.message_post(body=msg_body)
                                        subscription.set_to_renew()
                                if auto_commit:
                                    cr.commit()
                            except Exception:
                                if auto_commit:
                                    cr.rollback()
                                # we assume that the payment is run only once a day
                                traceback_message = traceback.format_exc()
                                _logger.error(traceback_message)
                                last_tx = self.env['payment.transaction'].search([('reference', 'like',
                                                                                   'SUBSCRIPTION-%s-%s' % (subscription.id,
                                                                                                           datetime.date.today().strftime(
                                                                                                               '%y%m%d')))],
                                                                                 limit=1)
                                error_message = "Error during renewal of subscription %s (%s)" % (subscription.code,
                                                                                                  'Payment recorded: %s' % last_tx.reference if last_tx and last_tx.state == 'done' else 'No payment recorded.')
                                _logger.error(error_message)

                    # invoice only
                    elif subscription.template_id.payment_mode in ['draft_invoice', 'manual', 'validate_send']:
                        try:
                            # We don't allow to create invoice past the end date of the contract.
                            # The subscription must be renewed in that case
                            if subscription.date and subscription.recurring_next_date >= subscription.date:
                                return
                            else:
                                invoice_values = subscription.with_context(
                                    lang=subscription.partner_id.lang)._prepare_invoice()
                                new_invoice = Invoice.create(invoice_values)
                                '''
                                    Esto se encarga de completar la información necesaria para que el documento pueda emitirse ante MH 
                                '''
                                company = self.env.user.company_id
                                if new_invoice.partner_id.payment_methods_id:
                                    new_invoice.payment_methods_id = new_invoice.partner_id.payment_methods_id.id
                                else:
                                    # El id = 5 equivale a Recaudado por tercero
                                    new_invoice.payment_methods_id = 5
                                new_invoice.economic_activity_id = company.activity_id

                                if subscription.analytic_account_id or subscription.tag_ids:
                                    for line in new_invoice.invoice_line_ids:
                                        if subscription.analytic_account_id:
                                            line.analytic_account_id = subscription.analytic_account_id
                                        if subscription.tag_ids:
                                            line.analytic_tag_ids = subscription.tag_ids

                                new_invoice.message_post_with_view(
                                    'mail.message_origin_link',
                                    values={'self': new_invoice, 'origin': subscription},
                                    subtype_id=self.env.ref('mail.mt_note').id)
                                invoices += new_invoice
                                # When `recurring_next_date` is updated by cron or by `Generate Invoice` action button,
                                # write() will skip resetting `recurring_invoice_day` value based on this context value
                                subscription.with_context(skip_update_recurring_invoice_day=True).increment_period()
                                if subscription.template_id.payment_mode == 'validate_send':
                                    subscription.validate_and_send_invoice(new_invoice)
                                if automatic and auto_commit:
                                    cr.commit()
                        except Exception:
                            if automatic and auto_commit:
                                cr.rollback()
                                _logger.exception('Fail to create recurring invoice for subscription %s',
                                                  subscription.code)
                            else:
                                raise
        return invoices

    def write(self, vals,):
        #Si se modifican ambas
        #if vals.get('colaborator_gestor',False) and vals.get('costumer_condition',False):

        #   body_str="""Gestor: """+ str(self.colaborator_gestor.name)  +" → "+ str(self.env['res.users'].browse(vals.get('colaborator_gestor')).name)
        #   self.message_post(body=body_str)

        #  body_str="""Condición de cliente ha sido modificada
        #      """ +str(self.costumer_condition)+" → "+str(vals.get('costumer_condition'))
        #   self.message_post(body=body_str)
        
        # Si se modifica el gestor
        if vals.get('colaborator_gestor',False):
            body_str="""Gestor: """+ str(self.colaborator_gestor.name)  +" ➞ "+ str(self.env['res.users'].browse(vals.get('colaborator_gestor')).name)

            self.message_post(body=body_str)
        
        # Si se modifica la condición del cliente
        if vals.get('costumer_condition',False):
            body_str="""Condición de cliente: 
                """ +str(dict(self._fields['costumer_condition'].selection).get(self.costumer_condition))+" ➞ "
            if vals.get('costumer_condition')=="highrisk":
                body_str+="Cliente de alto riesgo"
            if vals.get('costumer_condition')=="normal":
                body_str+="Cliente Normal"
            if vals.get('costumer_condition')=="dxx2":
                body_str+="DX X2"
            if vals.get('costumer_condition')=="dxmoroso":
                body_str+="DX Moroso"
        
            self.message_post(body=body_str)


        permitidos = ['img_placa',
                'img_placa_name',
                'contract_latitude',
                'contract_longitude',
                'gmaps',
                'resp_armada',
                'cuen_SIS',
                'contract_base',
                'n_usuarios',
                'n_contactos',
                'p_claves',
                'n_temp',
                'auto_beep_mail',
                'senna_recurrente',
                'kit_alarma',
                'telecom_number',
                'app_serial',
                'app_sim',
                'gsm_number',
                'recarga',
                'proveedor_sim',
                'tipo_panel',
                'ubica_panel',
                'tipo_teclado',
                'ubica_teclado',
                'ubica_sirena',
                'llaves_rf',
                'descrip_zonas',
                'equipo_adicional',
                'aperturas_app',
                'cierre_total_parcial',
                'coaccion',
                'alarma_teclado',
                'panel_sabotaje',
                'alarma_zonas',
                'kit_cctv',
                'dominio',
                'serie_dvr',
                'ubica_dvr',
                'f_contrato',
                'f_instalacion',
                'tecnico_instalador',
                'notas_tec',
                'notas_opera',
                'partner_direction',
                'camaras_ids',
                #Se permiten los comentarios para que se actualicen
                'com_calificado',
                'com_propuesta',
                'com_formalizacion',
                'com_valida_doc',
                'com_cuenta_monitoreo',
                'com_coordinacion',
                'com_instalacion',
                'com_valida_cuenta',
                'com_soporte',
                'com_conta',
                'com_finalizado',
                'has_comments',
                'ticket_count',
                'has_comments',
                "enlace_compass"
            ]
        if self.user_has_groups('tir_sisea_custom.group_subs_manager'):
            _logger.info(_("SUBS - Dentro de: user_has_groups"))
            for val in vals:
                _logger.info(_("SUBS - Valor de val: " + val))
                if val not in permitidos:
                    _logger.info(_("SUBS - val no esta dentro de permitidos"))
                    raise UserError(_("Validar los campos, usted solo tiene permiso de modificar 'Validación de Contrato'"))
        res = super(SaleSubscriptionSISEA, self).write(vals)
        return res

    @api.model
    def create(self, vals):
        permitidos = ['img_placa',
                'img_placa_name',
                'img_placa',
                'img_placa_name',
                'contract_latitude',
                'contract_longitude',
                'gmaps',
                'resp_armada',
                'cuen_SIS',
                'contract_base',
                'n_usuarios',
                'n_contactos',
                'p_claves',
                'n_temp',
                'auto_beep_mail',
                'senna_recurrente',
                'kit_alarma',
                'telecom_number',
                'app_serial',
                'app_sim',
                'gsm_number',
                'recarga',
                'proveedor_sim',
                'tipo_panel',
                'ubica_panel',
                'tipo_teclado',
                'ubica_teclado',
                'ubica_sirena',
                'llaves_rf',
                'descrip_zonas',
                'equipo_adicional',
                'aperturas_app',
                'cierre_total_parcial',
                'coaccion',
                'alarma_teclado',
                'panel_sabotaje',
                'alarma_zonas',
                'kit_cctv',
                'dominio',
                'serie_dvr',
                'ubica_dvr',
                'f_contrato',
                'f_instalacion',
                'tecnico_instalador',
                'notas_tec',
                'notas_opera',
                'partner_direction',
                'camaras_ids',
                #Se permiten los comentarios para que se actualicen
                'com_calificado',
                'com_propuesta',
                'com_formalizacion',
                'com_valida_doc',
                'com_cuenta_monitoreo',
                'com_coordinacion',
                'com_instalacion',
                'com_valida_cuenta',
                'com_soporte',
                'com_conta',
                'com_finalizado',
                'has_comments',
                'ticket_count',
                'has_comments',
                "enlace_compass"
            ]
        if self.user_has_groups('tir_sisea_custom.group_subs_manager'):
            for val in vals:
                if val not in permitidos:
                    raise UserError(_("Validar los campos, usted solo tiene permiso de modificar 'Validación de Contrato'"))
        res = super(SaleSubscriptionSISEA, self).create(vals)

        return res

    def _prepare_invoice_data(self):
        res = super()._prepare_invoice_data()

        company = self.env.user.company_id
        if self.partner_id.payment_methods_id:
            res['payment_methods_id'] = self.partner_id.payment_methods_id.id
        else:
            # El id = 5 equivale a Recaudado por tercero
            res['payment_methods_id'] = 5
        res['economic_activity_id'] = company.activity_id.id

        return res

    def validate_and_send_invoice(self, invoice):
        self.ensure_one()

        # Primero Validamos si tiene documentos sin pagar
        tolerancia = invoice.company_id.tolerancia_documentos

        invoices = self.env['account.move'].sudo().search([('partner_id', '=', invoice.partner_id.id), ('invoice_origin', '=', invoice.invoice_origin), ('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial']), ('move_type', '=', 'out_invoice')])

        if len(invoices) < tolerancia:
            invoice.action_post()
        else:
            fact_borrador = self.env.ref('tir_sisea_custom.fact_borrador')
            self.template_id = fact_borrador.id
            self.pendiente_de_validar = True

    def action_disable_validar(self):
        self.pendiente_de_validar = False
class SaleSubscriptionSISEACamaras(models.Model):
    _name = "sale.subscription.camaras.line"
    _description = "Camaras Contrato"


    camara_id = fields.Many2one(
        comodel_name='sale.subscription',
        string='Documento'
    )

    secuencia = fields.Integer('Secuencia')

    serial_camara = fields.Char(string="Serial WiFi Cámara", required=False)

    ubicacion_camara = fields.Text(string="Ubicación Cámara", required=False)

class SaleSubscriptionSISEASoporte(models.Model):
    _name = "sale.subscription.soporte"
    _description = "Helpdesk Contacts"


    sub_id = fields.Many2one(
        comodel_name='sale.subscription',
        string='Documento'
    )

    def _get_name(self):
        for rec in self:
            if rec.partner_id:
                rec.name = rec.partner_id.name
            else:
                rec.name = False

    name = fields.Char(string='Nombre', compute=_get_name)
    

    secuencia = fields.Integer('Secuencia')

    partner_id = fields.Many2one('res.partner', string="Contacto")

    parent_id = fields.Many2one('res.partner', string="Parent Assigned", required=True)
