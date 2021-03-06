# -*- coding: utf-8 -*-
{
    'name': "Telephony for ISPs",

    'summary': """
        Module to manage ISP telephony tasks and invoicing""",

    'description': """
        Module to Manage ISP telephony tasks and invoicing

        - Import CDR files
        - Import Rate files
        - Manage Rates by supplier
        - Manage telephony products with flat rate to specific destinations
        - Invoice CDR lines
        - Print call details in invoice with wkhtmltopdf
    """,

    'author': "Impulzia",
    'website': "https://odoo.space",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Accounting & Finance',
    'version': '0.2',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'analytic', 'account_analytic_analysis', 'product'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'templates.xml',
        'views/telephony_isp.xml',
        'views/telephony_wizard.xml',
        'views/product.xml',
        'views/invoice.xml',
        'views/contract.xml',
        'views/report_invoice_calls_detail.xml'
    ],
    # only loaded in demonstration mode
    #'demo': [
    #    'demo.xml',
    #],
    'installable': True,
    #'auto_install': False,
}
