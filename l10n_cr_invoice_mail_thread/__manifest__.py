# -*- coding: utf-8 -*-
{
        "name": "Receptor de Documentos Electrónicos",
        "version": '14.0.1.0.0',
        "author": "Norlan Ruiz - TI Recursos S.A.",
        'license': 'LGPL-3',
        "category" : "email",
        "summary": """Recepción documentos""",
        "description": """Receptor de Documentos Electrónicos""",
        'depends': [
                'base',
                'fetchmail',
                'mail',
                'l10n_cr_invoice',
        ],
        "data": [
                'security/ir.model.access.csv',
                # 'data/ir_cron_data.xml',
                'views/fetchmail.xml',
                'views/account_move_receptor.xml',
                ],
        "installable": True
}
