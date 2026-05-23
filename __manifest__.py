{
    'name': 'Blocked Routes Map Viewer',
    'version': '18.0.1.0.0',
    'category': 'Operations/Maps',
    'summary': 'Visor de Rutas bloqueadas por cronograma de lectura',
    'author': 'Antigravity',
    'depends': ['base', 'web'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/blocked_route_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Include Leaflet CSS/JS
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            
            # App Assets
            'block_routes/static/src/css/map_view.css',
            'block_routes/static/src/xml/map_view.xml',
            'block_routes/static/src/js/map_view.js',
        ],
    },
    'external_dependencies': {
        'python': ['shapefile'],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
