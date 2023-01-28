# -*- coding: utf-8 -*-

{
    'name': 'TI Recursos - Subscription Price Updater',
    'version': '14.0.1.0.1',
    'author': 'TI Recursos S.A.',
    'license': 'GPL-3',
    'website': 'https://www.tirecursos.com',
    'category': 'Customizations',
    'description':
        '''
        ''',
    'depends': ['sale_subscription'],
    'data': [
        'security/group_users.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/chance_price_subscription.xml',
        'views/action_manager.xml',
    ],
    'installable': True,
}
