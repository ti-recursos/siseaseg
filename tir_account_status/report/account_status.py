# -*- coding: utf-8 -*-
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
    _name = 'report.tir_account_status.account_status_report_view'

    @api.model
    def _get_report_values(self, docids, data=None):
        now_utc = datetime.now(pytz.timezone('UTC'))
        now_cr = now_utc.astimezone(pytz.timezone('America/Costa_Rica'))
        dia = now_cr.strftime('%d')  # '%02d' % now_cr.day,
        mes = now_cr.strftime('%m')  # '%02d' % now_cr.month,
        anno = now_cr.strftime('%Y')  # str(now_cr.year)[2:4],

        date_cr = now_cr.strftime(anno + "-" + mes + "-" + dia + "T%H:%M:%S")

        date_start = data['form']['date_start']
        date_end = data['form']['date_end']
        partner_id = data['form']['partner_id']

        draft_docs = data['form']['draft_docs']


        partner = self.env['res.partner'].search([('id', '=', partner_id)], limit=1)

        por_cobrar = partner.property_account_receivable_id.id
        por_pagar = partner.property_account_payable_id.id

        fin = datetime.strptime(str(date_end), '%Y-%m-%d').strftime("%d/%m/%Y")


        if draft_docs:
            dominio = [('date', '<=', date_end),
            ('parent_state', 'in', ['posted', 'draft']),
            ('partner_id', '=', partner_id),
            ('date', '>=', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)
            ]
        else:
            dominio = [('date', '<=', date_end), 
            ('parent_state', '=', 'posted'),
            ('partner_id', '=', partner_id),
            ('date', '>=', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)
            ]

        lineas = self.env['account.move.line'].search(
            dominio, order="date asc, account_id")

        docs = []
        cxc = []
        cxp = []
        ahora = datetime.strptime(now_utc.strftime("%Y-%m-%d"), "%Y-%m-%d")

        total_debito = 0
        total_credito = 0
        balance = 0
        balance_inicial = 0

        if draft_docs:
            dominio_balance = [
            ('parent_state', 'in', ['posted', 'draft']),
            ('partner_id', '=', partner_id),
            ('date', '<', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)]
            
        else:
            dominio_balance = [
            ('parent_state', '=', 'posted'),
            ('partner_id', '=', partner_id),
            ('date', '<', date_start),('product_id', '=', False)
            ,'|', ('account_id', '=', por_cobrar),('account_id', '=', por_pagar)]

        lineas_balance = self.env['account.move.line'].search(dominio_balance, order="date asc")
        for registro in lineas_balance:
            balance += registro.balance
            balance_inicial += registro.balance

        for linea in lineas:
            total_debito += linea.debit
            total_credito += linea.credit

            balance += linea.balance

            if linea.parent_state == 'draft':
                nombre = str(linea.move_id.id)
            else:
                nombre = linea.move_name

            docs.append({
                'date': linea.date,
                'name': nombre,
                'ref': linea.ref,
                'debit': linea.debit,
                'credit': linea.credit,

                'company': self.env.user.company_id,
                'balance': balance,
            })

        now_utc = datetime.now(pytz.timezone('UTC'))
        ahora = datetime.strptime(now_utc.strftime("%Y-%m-%d"), "%Y-%m-%d")

        '''

        # Documentos por pagar

        if draft_docs:
            dominio_cxp = [
            ('partner_id', '=', partner_id),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('state', 'in', ['posted', 'draft']),
            ('payment_state', 'in', ['not_paid', 'in_payment'])]
            
        else:
            dominio_cxp = [
            ('partner_id', '=', partner_id),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'in_payment'])]

        cxp_docs = self.env['account.move'].search(dominio_cxp, order="date asc")

        sin_vencer = 0
        grupo1_30 = 0
        grupo31_60 = 0
        grupo61_90 = 0
        grupo_m_91 = 0
        total_cxp = 0

        for linea in cxp_docs:
            if linea.invoice_date_due:
                vencimiento = datetime.strptime(linea.invoice_date_due.strftime("%Y-%m-%d"), "%Y-%m-%d")
            else:
                if linea.invoice_date:
                    vencimiento = datetime.strptime(linea.invoice_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                else:
                    vencimiento = datetime.strptime(linea.date.strftime("%Y-%m-%d"), "%Y-%m-%d")

            diff = ahora - vencimiento
            days, seconds = diff.days, diff.seconds
            total_cxp += linea.amount_residual_signed
            if days <= 0:
                sin_vencer += linea.amount_residual_signed
            elif 0 < days <= 30:
                grupo1_30 += linea.amount_residual_signed
            elif 30 < days <= 60:
                grupo31_60 += linea.amount_residual_signed
            elif 60 < days <= 90:
                grupo61_90 += linea.amount_residual_signed
            elif days > 90:
                grupo_m_91 += linea.amount_residual_signed

        cxp.append({
            'sin_vencer': sin_vencer,
            'grupo1_30': grupo1_30,
            'grupo31_60': grupo31_60,
            'grupo61_90': grupo61_90,
            'grupo_m_91': grupo_m_91,
            'total': total_cxp,
        })

        '''


        '''
            Documentos por cobrar
        '''

        if draft_docs:
            dominio_cxc = [
            ('partner_id', '=', partner_id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'in', ['posted', 'draft']),
            ('payment_state', 'in', ['not_paid', 'in_payment'])]
            
        else:
            dominio_cxc = [
            ('partner_id', '=', partner_id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'in_payment'])]

        cxc_docs = self.env['account.move'].search(dominio_cxc, order="date asc")

        sin_vencer = 0
        grupo1_30 = 0
        grupo31_60 = 0
        grupo61_90 = 0
        grupo_m_91 = 0
        total_cxc = 0

        for linea in cxc_docs:
            if linea.invoice_date_due:
                vencimiento = datetime.strptime(linea.invoice_date_due.strftime("%Y-%m-%d"), "%Y-%m-%d")
            else:
                if linea.invoice_date:
                    vencimiento = datetime.strptime(linea.invoice_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                else:
                    vencimiento = datetime.strptime(linea.date.strftime("%Y-%m-%d"), "%Y-%m-%d")

            diff = ahora - vencimiento
            days, seconds = diff.days, diff.seconds
            total_cxc += linea.amount_residual_signed

            if days <= 0:
                sin_vencer += linea.amount_residual_signed
            elif 0 < days <= 30:
                grupo1_30 += linea.amount_residual_signed
            elif 30 < days <= 60:
                grupo31_60 += linea.amount_residual_signed
            elif 60 < days <= 90:
                grupo61_90 += linea.amount_residual_signed
            elif days > 90:
                grupo_m_91 += linea.amount_residual_signed

        cxc.append({
            'sin_vencer': sin_vencer,
            'grupo1_30': grupo1_30,
            'grupo31_60': grupo31_60,
            'grupo61_90': grupo61_90,
            'grupo_m_91': grupo_m_91,
            'total': total_cxc,
        })


        return {
            'doc_ids': data['ids'],
            'doc_model': data['model'],
            'creacion': date_cr,
            'date_end': fin,
            'partner_id': partner,
            'total_debito': total_debito,
            'total_credito': total_credito,
            'balance_inicial': balance_inicial,
            'total_balance': balance,
            'total_lineas': balance,
            'company_id': self.env.user.company_id,
            'docs': docs,
            'cxc': cxc,
            'cxp': cxp,
        }

