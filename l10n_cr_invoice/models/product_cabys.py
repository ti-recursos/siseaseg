from odoo import fields, models, api, _

import logging
_logger = logging.getLogger(__name__)


import requests
from datetime import datetime
from odoo.exceptions import UserError


class ProductCabys(models.Model):
    _name = 'product.cabys'
    _description = "Product CABYS"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name')
    cabys_code = fields.Char(string='CABYS Code')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    tax_percent = fields.Float(string='Tax (%)', default=0.0)
    tax_ids_s = fields.Many2many(
        'account.tax', 'product_tax_s', 'id', 'tax_ids_s',
        string="Sales Taxes",
        domain=[('type_tax_use', '=', 'sale')],
        help="Taxes that apply on the base amount")

    tax_ids_p = fields.Many2many(
        'account.tax', 'product_tax_p', 'id', 'tax_ids_p',
        string="Purchase Taxes",
        domain=[('type_tax_use', '=', 'purchase')],
        help="Taxes that apply on the base amount")


    sale_ok = fields.Boolean(string="Sales", required=False, default=False)
    purchase_ok = fields.Boolean(string="Purchase", required=False, default=False)

    def action_update(self):

        productos = self.env['product.template'].sudo().search([('cabys_code_id', '=', self.id)])
        total_product = len(productos)
        for product in productos:
            msg_product = _('El usuario: %s, actualizó el código CABYS de: %s a %s') % (
            self.env.user.name, product.cabys_code, self.cabys_code)
            product.message_post(body=msg_product)

            product.cabys_code = self.cabys_code
            if self.sale_ok and product.sale_ok:
                product.taxes_id = self.tax_ids_s
            if self.purchase_ok and product.purchase_ok:
                product.supplier_taxes_id = self.tax_ids_p
        msg_body = _(
            'Se actualizaron un total de %s productos, con el código CABYS: %s') % (str(total_product), self.cabys_code)
        self.message_post(body=msg_body)

        productos = self.env['product.product'].sudo().search([('cabys_code_id', '=', self.id)])
        for product in productos:
            msg_product = _('El usuario: %s, actualizó el código CABYS de: %s a %s') % (
                self.env.user.name, product.cabys_code, self.cabys_code)
            product.message_post(body=msg_product)

            product.cabys_code = self.cabys_code
            if self.sale_ok and product.sale_ok:
                product.taxes_id = self.tax_ids_s
            if self.purchase_ok and product.purchase_ok:
                product.supplier_taxes_id = self.tax_ids_p


    @api.onchange('cabys_code')
    @api.depends('sale_ok', 'purchase_ok')
    def _cabys_code_changed(self):
        if not self.sale_ok and not self.purchase_ok and self.cabys_code:
            self.cabys_code = False
            raise UserError(_('Por favor indicar si es para compras y/o ventas'))
        if self.cabys_code and self.cabys_code.isdigit():
            url_base = self.company_id.url_base_cabys

            # Valida que existan el campo url_base
            if url_base:
                # Limpia caracteres en blanco en los extremos
                url_base = url_base.strip()

                # Elimina la barra al final de la URL para prevenir error al conectarse
                if url_base[-1:] == '/':
                    url_base = url_base[:-1]

                end_point = url_base + 'codigo=' + self.cabys_code

                headers = {
                    'content-type': 'application/json',
                }

                # Petición GET a la API
                peticion = requests.get(end_point, headers=headers, timeout=10)

                ultimo_mensaje = 'Fecha/Hora: ' + str(datetime.now()) + ', Codigo: ' + str(
                    peticion.status_code) + ', Mensaje: ' + str(peticion._content.decode())
                self.env.cr.execute("UPDATE  res_company SET ultima_respuesta_cabys='%s' WHERE id=%s" % (
                    ultimo_mensaje, self.env.user.company_id.id))

                if peticion.status_code == 200:
                    obj_json = peticion.json()
                    if (len(obj_json)) > 0:
                        for etiquetas in obj_json:
                            print(etiquetas)
                            if self.sale_ok:
                                sales = [('type_tax_use', '=', 'sale'),
                                         ('amount', '=', float(etiquetas['impuesto'])),
                                         ('tax_code', '=', '01'),
                                         ('iva_tax_desc', '!=', ''),
                                         ('iva_tax_code', '!=', '')]
                                taxes = self.env['account.tax'].search(sales)
                                self.tax_ids_s = taxes
                            if self.purchase_ok:
                                purchase = [('type_tax_use', '=', 'purchase'),
                                            ('amount', '=', float(etiquetas['impuesto'])),
                                            ('tax_code', '=', '01'),
                                            ('iva_tax_desc', '!=', ''),
                                            ('iva_tax_code', '!=', '')]
                                taxes = self.env['account.tax'].search(purchase)
                                self.tax_ids_p = taxes

                            self.tax_percent = float(etiquetas['impuesto'])
                            self.name = etiquetas['descripcion']

                    else:
                        # Por mejorar -> Se debe limpiar el campo de impuestos
                        raise UserError(_('Ocurrió un error al consultar el código: ' + str(
                            self.cabys_code) + ', por favor verifiquelo y vuelva a intentarlo'))
                else:
                    # Por mejorar -> Se debe limpiar el campo de impuestos
                    raise UserError(_('El servicio de Hacienda no está disponible en este momento'))
        else:
            if self.cabys_code and self.cabys_code.isalpha():
                url_base = self.env.user.company_id.url_base_cabys

                # Valida que existan el campo url_base
                if url_base:
                    # Limpia caracteres en blanco en los extremos
                    url_base = url_base.strip()

                    # Elimina la barra al final de la URL para prevenir error al conectarse
                    if url_base[-1:] == '/':
                        url_base = url_base[:-1]

                    end_point = url_base + 'q=' + self.cabys_code

                    headers = {
                        'content-type': 'application/json',
                    }

                    # Petición GET a la API
                    peticion = requests.get(end_point, headers=headers, timeout=10)

                    if peticion.status_code == 200:
                        obj_json = peticion.json()
                        if (len(obj_json['cabys'])) > 0:
                            codes = 'A continuación se muestra una lista de: ' + str(
                                len(obj_json['cabys'])) + ', con los códigos CAByS que cumplen el criterio: \n\n'
                            sorted_obj = sorted(obj_json['cabys'], key=lambda x: x['descripcion'], reverse=False)
                            for etiquetas in sorted_obj:
                                codes += 'Código: ' + str(etiquetas['codigo']) + '  |  Impuesto:' + str(
                                    float(etiquetas['impuesto'])) + '%'
                                codes += '\n'
                                codes += 'Descripción: ' + str(etiquetas['descripcion'])
                                codes += '\n\n'
                            raise UserError(_(codes))
                        else:
                            # Por mejorar -> Se debe limpiar el campo de impuestos
                            raise UserError(_('Ocurrió un error al consultar el código: ' + str(
                                self.cabys_code) + ', por favor verifiquelo y vuelva a intentarlo'))
                    else:
                        # Por mejorar -> Se debe limpiar el campo de impuestos
                        raise UserError(_('El servicio de Hacienda no está disponible en este momento'))