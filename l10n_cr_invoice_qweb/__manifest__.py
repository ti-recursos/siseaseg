# -*- coding: utf-8 -*-

{
    'name' : 'Costa Rica Electronic Invoice QWEB template',
    'version' : '14.0.1.0.0',
    'author' : 'TI Recursos S.A.',
    'summary': 'Update Invoice QWEB template to meet DGT requirements for Costa Rica',
    'description': """
Update Invoice QWEB template to meet DGT requirements for Costa Rica
    """,
    'category': 'Accounting & Finance',
    'sequence': 4,
    'website' : 'http://cysfuturo.com',
    'depends' : ['l10n_cr_invoice'],
    'demo' : [],
    'data' : [
        'views/report_sales_invoice_qweb.xml',
        'views/res_company_view.xml',
    ],
    'test' : [
    ],
    'auto_install': False,
    'application': True,
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
