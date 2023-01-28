# -*- coding: utf-8 -*-

{
    'name': 'Costa Rica Currency Adapter',
    'version': '14.0.1.0.0',
    'category': 'Account',
    'author': "TI Recursos S.A.",
    'website': 'https://www.tirecursos.com',
    'license': 'AGPL-3',
    'depends': ['base', 'account'],
    'data': [
        'data/currency_data.xml',
        'views/res_currency_rate_view.xml',
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {'python': ['zeep']},
    'installable': True,
    'auto_install': False,
}
