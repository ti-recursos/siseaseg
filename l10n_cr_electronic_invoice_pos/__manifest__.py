# -*- coding: utf-8 -*-
{
        "name": "Facturación Electrónica Costa Rica POS",
        "version": '14.0.1.0.0',
        "author": "Norlan Ruiz, TI Recursos S.A.",
        'license': 'LGPL-3',
        "website": "https://github.com/norubo/odoo-tir",
        "category": "API",
        "summary": """Configuración de Factura electrónica para POS""",
        "description": """Configuración de Factura electrónica para POS""",
        "depends": ['base', 'l10n_cr_invoice', 'point_of_sale'],

        "data": [
                'data/payment_methods_data.xml',
                'views/assets.xml',
                'views/pos_config.xml',
                'views/report_saledetails.xml'
        ],
        "installable": True,
        'qweb': [
                'static/src/xml/SaleDetailsReport.xml',
                'static/src/xml/pos.xml',
                'static/src/xml/order_line.xml',
                'static/src/xml/ClientDetailsEdit.xml',
        ],
}
