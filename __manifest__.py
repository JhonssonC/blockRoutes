{
    'name': 'Blocked Routes Map Viewer',
    'version': '18.0.1.0.0',
    'category': 'Operations/Maps',
    'summary': 'Visor de Rutas bloqueadas por cronograma de lectura',
    'author': 'JhonssonC',
    'depends': ['base', 'web'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'wizard/blocked_route_import_wizard_views.xml',
        'views/res_company_views.xml',
        'views/blocked_route_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # App Assets
            'blockRoutes/static/src/css/map_view.css',
            'blockRoutes/static/src/xml/map_view.xml',
            'blockRoutes/static/src/js/map_view.js',
        ],
    },
    'external_dependencies': {
        'python': ['shapefile', 'pandas', 'openpyxl'],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
