# -*- coding: utf-8 -*-
{
        "name" : "Consultar Información de Clientes en Hacienda Costa Rica",
        "version" : '14.0.1.0.0',
        "author" : "TI Recursos S.A.",
        'license': 'LGPL-3',
        "website" : "https://www.tirecursos.com",
        "category" : "API",
        "summary": """Consultar Nombre de Clientes en Hacienda Costa Rica""",
        "description": """Actualización automática de nombre de clientes a partir del API de Hacienda""",
        "depends" : ['base','contacts'],
        "data" : [
                'views/actualizar_clientes_view.xml'
                ],
        "installable": True
}
