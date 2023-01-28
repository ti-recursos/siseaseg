# -*- coding: utf-8 -*-

import re
import dateutil.parser

from odoo import fields,http
from odoo.http import request

import logging
_logger = logging.getLogger(__name__)

CODIGO = {
    '''
    Estos son los códigos de error enviados por el banco
    '''
    '00': 'Transaccion exitosa',
    '01': 'Cedula o Contrato no Existe',
    '02': 'Pagar en la Oficina',
    '03': 'No existe pago para esta reversion',
    '04': 'No se puede cancelar, hay pagos más antiguos',
    '05': 'Total recaudado por pagos no coincide',
    '06': 'Monto de comision no coincide',  # No se implementó
    '07': 'No existe pagos pendientes',
    '08': 'Ya esta afiliado',  # No se implementó
    '09': 'Ya esta desafiliado',  # No se implementó
    '''
    Estos son los códigos definidos por TI Recursos S.A.
    '''
    '10': 'No se encontro el parametro r',
    '11': 'No se encontraron todos los parametros esperados',
    '12': 'La fecha del pago y de la reversion son distintas',
    '13': 'Valor del parametro tipo inesperado',
    '14': 'No se encontro un banco que coincida con la informacion brindada',
    '15': 'Metodo inesperado',

}

class ApiCisa(http.Controller):

    @http.route('/api/cisa', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def metodos_web(self, **kwargs):
        if kwargs.get('r'):
            if kwargs['r'] == 'Status':
                res = "{'Codigo': '00'}"
            elif kwargs['r'] == 'Consulta':
                if (kwargs.get('id') and kwargs.get('tipo') and kwargs.get('convenio') and
                        kwargs.get('banco') and kwargs.get('agencia') and kwargs.get('fecha')):
                    if kwargs['tipo'] == '1':
                        partner_id = request.env['res.partner'].sudo().search([
                            ('vat', '=', kwargs['id'])
                        ])
                        if partner_id:
                            '''
                            subscription = request.env['sale.subscription'].sudo().search([('stage_id.in_progress','=',True),('partner_id.vat', '=', kwargs['id'])])
                            list_sub = []
                            for sub in subscription:
                                list_sub.insert(len(list_sub), sub.code)
                            '''
                            invoice_ids = request.env['account.move'].sudo().search([
                                ('partner_id.vat', '=', kwargs['id']),
                                ('payment_state', 'in', ['not_paid', 'partial']),
                                ('move_type', '=', 'out_invoice'),
                                ('state', 'in', ['posted','draft']),
                                ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                #('invoice_origin', 'in', list_sub),
                            ], limit=10, order="invoice_date asc")

                            res = self.consulta_respuesta(invoice_ids, partner_id)
                        else:
                            res = "{'Codigo': '01'}"
                    elif kwargs['tipo'] == '2':
                        subscription_id = request.env['sale.subscription'].sudo().search([
                            ('code', '=', kwargs['id'])
                        ])
                        if subscription_id:
                            invoice_ids = request.env['account.move'].sudo().search([
                                ('invoice_origin', '=', subscription_id.code),
                                ('payment_state', 'in', ['not_paid', 'partial']),
                                ('move_type', '=', 'out_invoice'),
                                ('state', 'in', ['posted', 'draft']),
                                ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                            ], limit=10, order="invoice_date asc")
                            res = self.consulta_respuesta(invoice_ids, subscription_id.partner_id)
                        else:
                            invoice_ids = request.env['account.move'].sudo().search([
                                ('invoice_origin', '=', kwargs['id']),
                                ('payment_state', 'in', ['not_paid', 'partial']),
                                ('move_type', '=', 'out_invoice'),
                                ('state', 'in', ['posted', 'draft']),
                                ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                            ], limit=10, order="invoice_date asc")
                            if len(invoice_ids) > 0:
                                res = self.consulta_respuesta(invoice_ids, invoice_ids.partner_id)
                            else:
                                res = "{'Codigo': '01'}"
                    else:
                        res = "{'Codigo': '13'}"
                else:
                    res = "{'Codigo': '11'}"
            elif kwargs['r'] == 'Pago':
                if (kwargs.get('id') and kwargs.get('tipo') and kwargs.get('convenio') and
                        kwargs.get('periodo') and kwargs.get('monto') and kwargs.get('factura') and
                        kwargs.get('banco') and kwargs.get('agencia') and kwargs.get('fecha')):
                    if kwargs['tipo'] == '1':
                        partner_id = request.env['res.partner'].sudo().search([
                            ('vat', '=', kwargs['id'])
                        ])
                        if partner_id:
                            factura = int(kwargs['factura'])
                            if len(str(factura)) < 11:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('partner_id.vat', '=', kwargs['id']),
                                    ('payment_state', 'in', ['not_paid', 'partial']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', 'in', ['posted', 'draft']),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('id', '=', factura)], limit=1)
                            else:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('partner_id.vat', '=', kwargs['id']),
                                    ('payment_state', 'in', ['not_paid', 'partial']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', 'in', ['posted', 'draft']),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('name', '=', factura)], limit=1)
                            if invoice_id:
                                res = self.pago_respuesta(invoice_id, partner_id, kwargs)
                            else:
                                res = "{'Codigo': '07'}"
                        else:
                            res = "{'Codigo': '01'}"
                    elif kwargs['tipo'] == '2':
                        subscription_id = request.env['sale.subscription'].sudo().search([
                            ('code', '=', kwargs['id'])
                        ])
                        if subscription_id:
                            factura = int(kwargs['factura'])
                            if len(str(factura)) < 11:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', subscription_id.code),
                                    ('payment_state', 'in', ['not_paid', 'partial']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', 'in', ['posted', 'draft']),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('id', '=', factura)
                                ], limit=1)
                            else:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', subscription_id.code),
                                    ('payment_state', 'in', ['not_paid', 'partial']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', 'in', ['posted', 'draft']),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('name', '=', factura)
                                ], limit=1)
                            if invoice_id:
                                res = self.pago_respuesta(invoice_id, subscription_id.partner_id, kwargs)
                            else:
                                res = "{'Codigo': '07'}"
                        else:
                            factura = int(kwargs['factura'])
                            if len(str(factura)) < 11:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', kwargs['id']),
                                    ('payment_state', 'in', ['not_paid', 'partial']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', 'in', ['posted', 'draft']),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('id', '=', factura)
                                ], limit=1)
                            else:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', kwargs['id']),
                                    ('payment_state', 'in', ['not_paid', 'partial']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', 'in', ['posted', 'draft']),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('name', '=', factura)
                                ], limit=1)
                            if invoice_id:
                                res = self.pago_respuesta(invoice_id, invoice_id.partner_id, kwargs)
                            else:
                                res = "{'Codigo': '01'}"
                    else:
                        res = "{'Codigo': '13'}"
                else:
                    res = "{'Codigo': '11'}"
            elif kwargs['r'] == 'Reversion':
                if (kwargs.get('id') and kwargs.get('tipo') and kwargs.get('convenio') and
                        kwargs.get('periodo') and kwargs.get('monto') and kwargs.get('factura') and
                        kwargs.get('banco') and kwargs.get('agencia') and kwargs.get('fecha')):
                    if kwargs['tipo'] == '1':
                        partner_id = request.env['res.partner'].sudo().search([
                            ('vat', '=', kwargs['id'])
                        ])
                        if partner_id:
                            factura = int(kwargs['factura'])
                            if len(str(factura)) < 11:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('partner_id.vat', '=', kwargs['id']),
                                    ('payment_state', 'in', ['paid', 'in_payment']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', '=', 'posted'),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('id', '=', factura)
                                ], limit=1)
                            else:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('partner_id.vat', '=', kwargs['id']),
                                    ('payment_state', 'in', ['paid', 'in_payment']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', '=', 'posted'),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('name', '=', factura)
                                    ], limit=1)
                            if invoice_id:
                                self.reversion_respuesta(invoice_id, kwargs)
                            else:
                                res = "{'Codigo': '07'}"
                        else:
                            res = "{'Codigo': '01'}"
                    elif kwargs['tipo'] == '2':
                        subscription_id = request.env['sale.subscription'].sudo().search([
                            ('code', '=', kwargs['id'])
                        ])
                        if subscription_id:
                            factura = int(kwargs['factura'])
                            if len(str(factura)) < 11:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', subscription_id.code),
                                    ('payment_state', 'in', ['paid', 'in_payment']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', '=', 'posted'),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('id', '=', factura)
                                ], limit=1)
                            else:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', subscription_id.code),
                                    ('payment_state', 'in', ['paid', 'in_payment']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', '=', 'posted'),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('name', '=', factura)
                                ], limit=1)
                            if invoice_id:
                                res = self.reversion_respuesta(invoice_id, kwargs)
                            else:
                                res = "{'Codigo': '07'}"
                        else:
                            factura = int(kwargs['factura'])
                            if len(str(factura)) < 11:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', kwargs['id']),
                                    ('payment_state', 'in', ['paid', 'in_payment']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', '=', 'posted'),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('id', '=', factura)
                                ], limit=1)
                            else:
                                invoice_id = request.env['account.move'].sudo().search([
                                    ('invoice_origin', '=', kwargs['id']),
                                    ('payment_state', 'in', ['paid', 'in_payment']),
                                    ('move_type', '=', 'out_invoice'),
                                    ('state', '=', 'posted'),
                                    ('state_tributacion', 'in', [False, 'procesando', 'aceptado']),
                                    ('name', '=', factura)
                                ], limit=1)
                            if invoice_id:
                                res = self.reversion_respuesta(invoice_id, kwargs)
                            else:
                                res = "{'Codigo': '01'}"
                    else:
                        res = "{'Codigo': '13'}"
                else:
                    res = "{'Codigo': '11'}"
#Nuevas implementaciones para BN PAR
        #Matricula
            elif kwargs['r'] == 'Matricula':
                if (kwargs.get('id') and kwargs.get('tipo') and kwargs.get('convenio') and
                        kwargs.get('banco') and kwargs.get('agencia') and kwargs.get('transaccion') and kwargs.get('fecha')):
                        #afiliación
                    if kwargs['transaccion'] == '100000':
                            subscription_id = request.env['sale.subscription'].sudo().search([('code', '=', kwargs['id'])])
                            if subscription_id:
                                if subscription_id.bnpar == False:
                                    subscription_id.bnpar = True
                                    res="""{'Codigo':'00','Nombre':'"""+str(subscription_id.partner_id.name)+"""'}"""
                                else:
                                    res="""{'Codigo':'08'}"""
                            else:
                                 res="""{'Codigo':'01'}"""
                        #desafiliación
                    elif kwargs['transaccion'] == '100001':
                            subscription_id = request.env['sale.subscription'].sudo().search([('code', '=', kwargs['id'])])
                            if subscription_id:
                                if subscription_id.bnpar:
                                    subscription_id.bnpar =  False
                                    res="""{'Codigo':'00','Nombre':'"""+str(subscription_id.partner_id.name)+"""'}"""
                                else:
                                    res="""{'Codigo':'09'}"""
                            else:
                                 res="""{'Codigo':'01'}"""
                        #Consulta
                    elif kwargs['transaccion'] == '100002':
                        subscription_id = request.env['sale.subscription'].sudo().search([('code', '=', kwargs['id'])])
                        if subscription_id:
                            res="""{'Codigo':'00','Nombre':'"""+str(subscription_id.partner_id.name)+"'}"
                        else:
                            res="""{'Codigo':'01'}"""
                else: 
                    res = "{'Codigo': '11'}"
            #Calendarizacion
            elif kwargs['r'] == 'Calendarizacion':
                if (kwargs.get('convenio') and kwargs.get('banco') and kwargs.get('agencia') and kwargs.get('transaccion') and
                    kwargs.get('fecha') and kwargs.get('ultimafactura') and kwargs.get('ultimoperiodo')):
                    subscription_id = request.env['sale.subscription'].sudo().search([('bnpar', '=', True)])
                    lista_cod = []
                    lista_invoices = []
                    for i in subscription_id:
                        lista_cod += [i.code]
                        invoice_id = request.env['account.move'].sudo().search([
                            ('invoice_origin', '=', i.code),
                            ('payment_state', 'in', ['not_paid', 'partial']),
                            ('move_type', '=', 'out_invoice'),
                            ('state', 'in', ['posted', 'draft']),
                            ('state_tributacion', 'in', [False, 'procesando', 'aceptado'])], limit=1)
                        lista_invoices += invoice_id
                    if len(lista_invoices) > 0:
                        ultimafactura = kwargs['ultimafactura']
                        res = self.calendarizacion_respuesta(lista_invoices,ultimafactura)
                    else:
                        res = "{'Codigo': '07'}"
                else:
                    res = "{'Codigo': '11'}"
            else:
                res = "{'Codigo': '15'}"
        else:
            res = "{'Codigo': '12'}"

        request.env['cisa'].sudo().create({
            'name': kwargs,
            'fch': fields.Datetime.now(),
            'res': res,
        })
        return res

#numero factura invoice.name
    def calendarizacion_respuesta(self, lista_invoices,ultimafactura):
        lista_invoices_name = []
        lista_invoices_clear = []
        mas_registros = 0
        for i in lista_invoices:
            if i.name == '/':
                lista_invoices_name.append(str(i.id))
            else:
                lista_invoices_name.append(i.name)
            
        #_logger.info("!JKA: "+str(lista_invoices_name))
        if ultimafactura in lista_invoices_name: #TODO: Verificar si ultima factura continua en la lista segunda ejecución, pago no pasa
            _logger.info("!JKA: "+str(i.name)+":"+str(i.id))
            flag = False
            for i in lista_invoices:
                if i.name == ultimafactura or i.id == int(ultimafactura):
                    flag = True
                    continue
                if flag:
                    lista_invoices_clear += i
        else:
            lista_invoices_clear = lista_invoices
        if len(lista_invoices_clear) > 10:
            mas_registros = 1

        pendientes = len(lista_invoices_clear)
        pendientes = pendientes - 10
        if pendientes < 0:
            pendientes  = 0
        res = {
            'Codigo': '00',
            'MasRegistros':str(mas_registros),
            'Pendientes':str(pendientes),
            'Facturas':[],
        }
        consolidado = []
        cont = 0
        for i in lista_invoices_clear:
            #Define el periodo de la factura
            fechaperiodo = i.periodo_sub
            periodo = fechaperiodo.strftime("%Y%m")
            #define el dia de vencimiento
            if i.invoice_date_due:
                dia = i.invoice_date_due
                dia_pago = dia.strftime("%Y%m%d")
            else:
                dia = i.invoice_date
                dia_pago = dia.strftime("%Y%m%d")
            if i.name == '/':
                documento = str(i.id)
            else:
                documento = i.name
            data = {
                        'Id': i.invoice_origin or '',
                        'Periodo': periodo,
                        'Monto': int(round(i.amount_residual * 100, 0)),
                        'Vencimiento': dia_pago,
                        'NumFactura': documento,
                        }
            consolidado.append(data)
            #Admite maximo 10 facturas por iteración.
            cont+=1
            if cont==10:
                break
            

        res['Facturas'] = consolidado
        return str(res)

    def consulta_respuesta(self, invoice_ids, partner_id):
        res = {
            'Codigo': '00',
            'Nombre': partner_id.name or '',
            'Pendientes': len(invoice_ids),
            'Facturas': [],
        }
        if invoice_ids:
            consolidado = []
            for invoice in invoice_ids:
                fechaperiodo = invoice.periodo_sub
                periodo = fechaperiodo.strftime("%Y%m")
                if invoice.invoice_date_due:
                    dia = invoice.invoice_date_due
                    dia_pago = dia.strftime("%Y%m%d")
                else:
                    dia = invoice.invoice_date
                    dia_pago = dia.strftime("%Y%m%d")
                if invoice.name == '/':
                    documento = invoice.id
                else:
                    documento = invoice.name
                data = {
                    'contrato': invoice.invoice_origin or '',
                    'factura': str(documento),
                    'periodo': periodo,
                    'monto': int(round(invoice.amount_residual * 100, 0)),
                    'dia_pago': dia_pago,
                }
                consolidado.append(data)
            res['Facturas'] = consolidado
        return str(res)

    def pago_respuesta(self, invoice_id, partner_id, kwargs):
        _logger.error('pago_respuesta')
        if invoice_id:
            if kwargs['banco'] == '100':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_100').id,
            elif kwargs['banco'] == '102':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_102').id,
            elif kwargs['banco'] == '151':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_151').id,
            elif kwargs['banco'] == '152':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_152').id,
            elif kwargs['banco'] == '500':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_500').id,
            else:
                journal_id = False
            _logger.error('pago_respuesta diario ')

            '''
                verificamos si posee documentos más antiguos sin pagar
            '''

            if invoice_id.invoice_date_due:
                dia = invoice_id.invoice_date_due
            else:
                dia = invoice_id.invoice_date

            antiguas = request.env['account.move'].sudo().search([
                ('partner_id', '=', invoice_id.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', 'in', ['draft', 'posted']),
                ('payment_state', 'in', ['not_paid', 'in_payment']),
                ('invoice_origin', '=', invoice_id.invoice_origin),
                ('invoice_date_due', '<', dia),
                ('id', '!=', invoice_id.id)
                ])
            _logger.error('Total de Documentos ' + str(len(antiguas)))
            for doc in antiguas:
                _logger.error('Documentos: ' + str(doc.name))
            if len(antiguas) == 0:

                if invoice_id.state == 'draft':
                    _logger.error('pago_respuesta documento borrador')
                    company = request.env['res.company'].search([('id', '=', invoice_id.company_id.id)])
                    invoice_id.economic_activity_id = company.activity_id
                    invoice_id.action_post()
                    _logger.error('pago_respuesta documento borrador generado')

                if journal_id:
                    ano = kwargs['fecha'][0:4]
                    mes = kwargs['fecha'][4:6]
                    dia = kwargs['fecha'][6:8]
                    fch = '{0}-{1}-{2}'.format(ano, mes, dia)

                    '''
                    En Odoo 14 no se utiliza account.payment para guardar un pago, sino que se debe realiza desde account.payment.register
                    '''
                    _logger.error('pago_respuesta creando pago')
                    payment_id = request.env['account.payment.register'].sudo().with_context(active_model='account.move', active_ids=invoice_id.ids).create({
                        'payment_date': dateutil.parser.parse(fch).date(),
                        'payment_method_id': request.env.ref('account.account_payment_method_manual_in').id,
                        'amount': float(kwargs['monto']) / 100,
                        'currency_id': invoice_id.currency_id.id,
                        'journal_id': journal_id,
                        'payment_type': 'inbound',
                        'partner_type': 'customer',
                        'partner_id': invoice_id.partner_id.id,
                    })
                    _logger.error('pago_respuesta pago creado id: %s' % payment_id.id)
                    pago = payment_id.action_create_payments()
                    _logger.error('pago_respuesta ejecutando action_create_payments() pago creado id: %s' % payment_id.id)
                    _logger.error('pago_respuesta action_create_payments')
                    payment = request.env['account.payment'].sudo().search([('id', '=', pago['res_id'])], limit=1)
                    if payment.state == 'draft':
                        payment.payment_method = 'cisa'
                        payment.action_post()
                    # Indico que el pago se está haciendo por medio de CISA
                    payment.payment_method = 'cisa'

                    invoice_id.payment_id = payment.id
                    _logger.error('pago_respuesta referenciando pago con factura')

                    if invoice_id.invoice_date_due:
                        _logger.error('pago_respuesta fecha de vencimiento invoice_date_due')
                        dia = invoice_id.invoice_date_due
                        dia_pago = dia.strftime("%Y%m%d")

                    _logger.error('pago_respuesta invoice_date_due')


                    tax_lines = invoice_id.line_ids.filtered(lambda line: line.tax_line_id)
                    tax_balance_multiplicator = -1 if invoice_id.is_inbound(True) else 1

                    # Impuestos

                    tax_cruz_roja = 0
                    tax_911 = 0
                    tax_iva = 0

                    for line in tax_lines:
                        if line.tax_line_id.tax_code == 'otroscargos':
                            if line.tax_line_id.iva_tax_desc == 'Cargo Cruz Roja':
                                tax_cruz_roja += tax_balance_multiplicator * (line.amount_currency if line.currency_id else line.balance)
                            elif line.tax_line_id.iva_tax_desc == 'Cargo 911':
                                tax_911 += tax_balance_multiplicator * (line.amount_currency if line.currency_id else line.balance)
                        else:
                            tax_iva += tax_balance_multiplicator * (line.amount_currency if line.currency_id else line.balance)

                    # Calculo el porcentaje que aplica del impuesto
                    monto_pago = float(kwargs['monto']) / 100

                    porcentaje = monto_pago / invoice_id.amount_total

                    tax_cruz_roja = tax_cruz_roja * porcentaje
                    tax_911 = tax_911 * porcentaje
                    tax_iva = tax_iva * porcentaje

                    monto_pago = monto_pago - (tax_cruz_roja + tax_911 + tax_iva)

                    rubro = {
                            'monto': str(int(round(monto_pago * 100, 0)))
                        }
                    '''
                        Codificacion:
                        0004 : monto
                        0006 : reconexion
                        0007 : multas
                        0008 : otros
                        0010 : iva
                        0011 : impuesto_911
                        0012 : impuesto_cruz_roja 
                    '''

                    if float(round(tax_iva, 2)) > 0:
                        rubro.update({'iva': str(int(round(tax_iva * 100, 0)))})

                    if float(round(tax_911, 2)) > 0:
                        rubro.update({'impuesto_911': str(int(round(tax_911 * 100, 0)))})

                    if float(round(tax_cruz_roja, 2)) > 0:
                        rubro.update({'impuesto_cruz_roja': str(int(round(tax_cruz_roja * 100, 0)))})

                    res = {
                        'Codigo': '00',
                        'Nombre': partner_id.name,
                        'Rubros': [rubro],
                    }
                else:
                    res = "{'Codigo': '14'}"
            else:
                res = "{'Codigo' : '04'}"
        else:
            res = "{'Codigo': '07'}"

        res = str(res).replace("'", '"')
        return res

    def reversion_respuesta(self, invoice_id, kwargs):
        if invoice_id:

            if kwargs['banco'] == '100':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_100').id,
            elif kwargs['banco'] == '102':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_102').id,
            elif kwargs['banco'] == '151':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_151').id,
            elif kwargs['banco'] == '152':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_152').id,
            elif kwargs['banco'] == '500':
                journal_id = request.env.ref('tir_api_cisa.journal_bank_500').id,
            else:
                journal_id = False

            monto = float(kwargs['monto']) / 100

            payment_ids = request.env['account.payment'].sudo().search([
                ('ref', '=', invoice_id.name),
                ('state', '=', 'posted'),
                ('partner_id', '=', invoice_id.partner_id.id),
                ('amount', '=', monto)
            ], limit=1)

            if payment_ids:
                mismo_dia = True
                diff_bank = True
                ano = kwargs['fecha'][0:4]
                mes = kwargs['fecha'][4:6]
                dia = kwargs['fecha'][6:8]

                for payment in payment_ids:
                    if payment.journal_id.id == journal_id[0]:
                        fch = dateutil.parser.parse('{0}-{1}-{2}'.format(ano, mes, dia)).date()
                        if payment.date != fch:
                            mismo_dia = False
                        # Se pasa a borrador
                        payment.action_draft()
                        # Se cancela el pago
                        payment.action_cancel()
                        payment.payment_method = 'cisa'
                    else:
                        diff_bank = False
                if diff_bank:
                    if mismo_dia:

                        fch = fields.Datetime.now().strftime("%Y%m%d%H%M%S")
                        res = {
                            'Codigo': '00',
                            'Fecha': fch,
                        }
                    else:
                        res = "{'Codigo': '12'}"
                else:
                    res = "{'Codigo': '03'}"
            else:
                res = "{'Codigo': '03'}"
        else:
            res = "{'Codigo': '07'}"
        return str(res)
