{
    'name': 'Administrador de Intereses',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': 'Calcule los intereses de los socios seleccionados',
    'author': 'Norlan Ruiz',
    'website': 'www.tirecursos.com',
    'license': 'AGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'views/res_company_views.xml',
        'data/ir_cron_data.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
