{
    'name': 'Account Status Report',
    'version': '14.0.1.0.0',
    'summary': '',
    'category': 'Account',
    'author': 'TI Recursos S.A., Norlan Ruiz',
    'maintainer': 'Norlan Ruiz',
    'website': 'https://soporte.tirecursos.com',
    'license': 'GPL-3',
    'contributors': [
    ],
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/action_manager.xml',
        'report/account_status.xml',
        'wizard/account_status_report_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
