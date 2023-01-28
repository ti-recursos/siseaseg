# -*- coding: utf-8 -*-
###################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2020-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###################################################################################
{
    'name': 'Reportes Factura Electrónica CR',
    'version': '14.0.1.0.0',
    "category": "account",
    'author': 'TI Recursos',
    'website': "https://www.tirecursos.com",
    'summary': """Reporte de Facturación - TI Recursos""",
    'description': """Reporte de Facturación - TI Recursos""",
    'depends': ['base', 'l10n_cr_invoice'],
    'license': 'AGPL-3',
    'data': ['security/ir.model.access.csv',
            'views/project_report.xml',
            'views/account_move.xml',
            'views/action_manager.xml',
            'views/res_partner.xml',
            'wizard/account_move_reports_custom.xml',
            'report/project_report_pdf_view.xml',
            'data/paper_landscape_letter.xml',
            'report/account_cxc_summary.xml',
            'wizard/account_cxc_report_view.xml',
            ],
    'installable': True,
    'auto_install': False,
}
