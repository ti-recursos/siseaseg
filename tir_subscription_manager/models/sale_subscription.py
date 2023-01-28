import logging
import datetime
import traceback
import pytz

from ast import literal_eval
from collections import Counter
from dateutil.relativedelta import relativedelta
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import format_date, float_compare
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)

class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    @api.model
    def _suscripciones(self, automatic=False):
        _logger.info('E-SUBS TIR - Ejecutando _suscripciones')
        facturas = self.env['account.move'].search([('state','=','draft'),('move_type','=','out_invoice')])

        for inv in facturas:
            if inv.invoice_origin:
                cliente = self.env['res.partner'].search([('id', '=', inv.partner_id.id)])
                company = self.env['res.company'].search([('id', '=', inv.company_id.id)])
                inv.payment_methods_id = cliente.payment_methods_id.id
                inv.economic_activity_id = company.activity_id

                # Se setean los campos en NULL para que el método action_post() se encarge de generarlos nuevamente

                inv.invoice_date = False
                inv.date_issuance = False
                inv.number_electronic = False
                inv.sequence = False
                inv.invoice_payment_term_id = cliente.property_payment_term_id

                # inv.action_post()
        _logger.info('E-SUBS TIR - _suscripciones - Finalizado Exitosamente')

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
                                new_invoice.economic_activity_id = company.activity_id

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
