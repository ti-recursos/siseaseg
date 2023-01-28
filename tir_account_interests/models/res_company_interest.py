##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)


class ResCompanyInterest(models.Model):

    _name = 'res.company.interest'
    _description = 'Account Interest'

    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        ondelete='cascade',
    )
    receivable_account_ids = fields.Many2many(
        'account.account',
        string='Cuentas a Cobrar',
        help='Cuentas a Cobrar que se tendrán en cuenta para evaular la deuda',
        required=True,
        domain="[('user_type_id.type', '=', 'receivable'),"
        "('company_id', '=', company_id)]",
    )
    invoice_receivable_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de factura por cobrar',
        help='Si no se selecciona ninguna cuenta, entonces se usa la cuenta por cobrar del socio',
        domain="[('user_type_id.type', '=', 'receivable'),"
        "('company_id', '=', company_id)]",
    )
    interest_product_id = fields.Many2one(
        'product.product',
        'Producto de interés',
        required=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        'Cuenta analítica',
    )
    rate = fields.Float(
        'Interés',
        required=True,
        help='Debe indicarlo de 0 a 1, siendo 1 el 100%',
        digits=(7, 4)
    )
    automatic_validation = fields.Boolean(
        'Validación Automática?',
        help='Validación automática de facturas?',
        default=True,
    )
    rule_type = fields.Selection([
        ('daily', 'Día(s)'),
        ('weekly', 'Semana(s)'),
        ('monthly', 'Mes(es)'),
        ('yearly', 'Año(s)'),
    ],
        'Recurrencia',
        help="La factura de intereses se repite automáticamente en el intervalo especificado",
        default='monthly',
    )
    interval = fields.Integer(
        'Repetir cada',
        default=1,
        help="Repetir cada (días / semana / mes / año)"
    )
    tolerance_interval = fields.Integer(
        'Tolerancia',
        default=1,
        help="Número de períodos de tolerancia a las cuotas. 0 = sin tolerancia"
    )
    next_date = fields.Date(
        'Fecha de la próxima factura',
        default=fields.Date.today,
    )
    domain = fields.Char(
        'Filtros adicionales',
        default="[]",
        help="Filtros adicionales que se agregarán a la búsqueda estándar"
    )
    has_domain = fields.Boolean(compute="_compute_has_domain")

    @api.model
    def _cron_recurring_interests_invoices(self):
        _logger.info('Running Interest Invoices Cron Job')
        current_date = fields.Date.today()
        self.search([('next_date', '<=', current_date)]
                    ).create_interest_invoices()


    def create_interest_invoices(self):
        for rec in self:
            _logger.info(
                'Creating Interest Invoices (id: %s, company: %s)', rec.id,
                rec.company_id.name)
            interests_date = rec.next_date

            rule_type = rec.rule_type
            interval = rec.interval
            tolerance_interval = rec.tolerance_interval
            # next_date = fields.Date.from_string(interests_date)
            if rule_type == 'daily':
                next_delta = relativedelta(days=+interval)
                tolerance_delta = relativedelta(days=+tolerance_interval)
            elif rule_type == 'weekly':
                next_delta = relativedelta(weeks=+interval)
                tolerance_delta = relativedelta(weeks=+tolerance_interval)
            elif rule_type == 'monthly':
                next_delta = relativedelta(months=+interval)
                tolerance_delta = relativedelta(months=+tolerance_interval)
            else:
                next_delta = relativedelta(years=+interval)
                tolerance_delta = relativedelta(years=+tolerance_interval)
            interests_date_date = fields.Date.from_string(interests_date)
            # buscamos solo facturas que vencieron
            # antes de hoy menos un periodo
            # TODO ver si queremos que tambien se calcule interes proporcional
            # para lo que vencio en este ultimo periodo
            to_date = fields.Date.to_string(
                interests_date_date - tolerance_delta)

            rec.create_invoices(to_date)

            # seteamos proxima corrida en hoy mas un periodo
            rec.next_date = fields.Date.to_string(interests_date_date + next_delta)


    def create_invoices(self, to_date):
        self.ensure_one()

        # Format date to customer langague
        # For some reason there is not context pass, not lang, so we
        # force it here
        lang_code = self.env.context.get('lang', self.env.user.lang)
        lang = self.env['res.lang']._lang_get(lang_code)
        date_format = lang.date_format
        to_date_format = fields.Date.from_string(
            to_date).strftime(date_format)

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)], limit=1)

        move_line_domain = [
            ('account_id', 'in', self.receivable_account_ids.ids),
            ('full_reconcile_id', '=', False),
            ('date_maturity', '<', to_date)
        ]

        # Check if a filter is set
        if self.domain:
            move_line_domain += safe_eval(self.domain)

        move_line = self.env['account.move.line']
        grouped_lines = move_line.read_group(
            domain=move_line_domain,
            fields=['id', 'amount_residual', 'partner_id', 'account_id'],
            groupby=['partner_id'],
        )
        self = self.with_context(mail_notrack=True, prefetch_fields=False)

        total_items = len(grouped_lines)
        _logger.info('%s interest invoices will be generated', total_items)

        for idx, line in enumerate(grouped_lines):

            debt = line['amount_residual']
            partner_id = line['partner_id'][0]

            partner = self.env['res.partner'].browse(partner_id)
            comment = self.prepare_info(to_date, debt)

            taxes = self.env['product.product'].search([('id', '=', self.interest_product_id.id)]).taxes_id.ids

            invoice = self.env['account.move'].create({
                'invoice_date': to_date_format,
                'type': 'out_invoice',
                'partner_id': partner.id,
                'journal_id': journal.id,
                'narration': comment,
                'economic_activity_id': self.company_id.activity_id.id,
                'currency_id': self.company_id.currency_id.id,
                'invoice_payment_term_id': partner.property_payment_term_id.id,
                'payment_methods_id': partner.payment_methods_id.id,
                'tipo_documento': 'ND',
                'fiscal_position_id': partner.property_account_position_id.id,
                'invoice_date': self.next_date,
                'company_id': self.company_id.id,
                'user_id': partner.user_id.id or False,
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.interest_product_id.id,
                    'quantity': 1.0,
                    'name': self.interest_product_id.name + self.prepare_info(to_date, debt),
                    'discount': 0.00,
                    'price_unit': self.rate * debt,
                    'tax_ids': taxes,
                })]
            })
            invoice.action_post()


    def prepare_info(self, to_date_format, debt):
        self.ensure_one()
        porcentaje = "{}%".format(self.rate * 100)
        res = _(
            'Deuda Vencida al %s: %s\n'
            'Tasa de interés: %s') % (
                  to_date_format, debt, porcentaje)

        return res

    @api.depends('domain')
    def _compute_has_domain(self):
        self.has_domain = len(safe_eval(self.domain)) > 0
