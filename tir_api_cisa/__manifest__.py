# -*- coding: utf-8 -*-

{
    'name': "API de integración CISA",
    'version': '14.0.1.0.0',
    'depends': [
        'sale_subscription',
        'l10n_cr_invoice',
        'account',
    ],
    'author': "TI Recursos",
    'category': 'Personalizaciones',
    'description': """
    API de integración CISA
    """,
    'data': [
        'security/ir.model.access.csv',
        'data/cisa_data.xml',
        'views/cisa_views.xml',
        'views/account_move.xml',
        'views/account_payment.xml',
        'views/sale_subscription.xml'
    ],
}