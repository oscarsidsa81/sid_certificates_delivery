# -*- coding: utf-8 -*-
{
    'name': 'SID Inventory Certificates',
    'version': '15.0.1.1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Consolidación técnica de certificados de inventario, recepciones, entregas y stock.move.line',
    'author': 'SIDSA',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'stock_picking_batch',
        'mail',
        'documents',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/inventory_certificate_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_production_lot_views.xml',
        'views/stock_picking_batch_views.xml',
        'views/certificate_wizard_views.xml',
        'data/server_actions.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
