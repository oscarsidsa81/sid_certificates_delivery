
{
    'name': "Expansión para mejora de eficiencia en caso de output de gran tamaño "
            "(sid_certificates_delivery)",
    'summary': """
        Realiza por lotes de MB y stock.move limitados para elaborar los
        certificados de inventario para las entregas""",
    'author': "oscarsidsa81",
    'website': "Suministros Industriales Diversos S.A",
    'category': 'Stock',
    'version': '15.0.1.0.0',
    # any module necessary for this one to work correctly
    'depends': ['oct_certificate_delivery'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/sid_picking_view.xml',
        'data/sid_server_action.xml',
    ],
}
