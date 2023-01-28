{
    'name' : 'Help_desk_frecuentquest',
    'version' : '	14.0.1.3',
    'summary': 'help_desk_new_add',
    'sequence': 1,
    'description': """
Help_desk_new
====================
Tipo de ticket y aparecer sus posibles preguntas y respuestas registradas
    """,
    'category': 'Hidden/Tools',
    'depends' : ['base','helpdesk','contacts'],
    'data': [
    'views/views_helpdesk_new.xml',
    'security/ir.model.access.csv'
    ],
    'application': False,
    'license': 'LGPL-3',
}