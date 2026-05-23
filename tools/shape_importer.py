import os
import json
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

try:
    import shapefile
except ImportError:
    shapefile = None
    _logger.warning("Libreria 'pyshp' no está instalada. Ejecute 'pip install pyshp' para importar shapefiles.")

def import_shapes_to_routes(env, directory_path='data/shapes/', name_attribute='NAME', business_unit=False):
    """
    Lee archivos Shapefile (.shp) desde un directorio y crea/actualiza 
    registros en block_routes.route como GeoJSON.
    """
    if not shapefile:
        _logger.error("No se puede importar: pyshp no está instalado.")
        return False
        
    full_path = os.path.join(env.cr.dbname, directory_path)
    # Por si se ejecuta usando rutas relativas al módulo
    import odoo.modules
    module_path = odoo.modules.get_module_path('block_routes')
    if module_path:
        full_path = os.path.join(module_path, directory_path)
        
    if not os.path.exists(full_path):
        _logger.error("El directorio de shapefiles no existe: %s", full_path)
        return False
        
    Route = env['block_routes.route']
    created_count = 0
    
    for filename in os.listdir(full_path):
        if filename.endswith(".shp"):
            shp_path = os.path.join(full_path, filename)
            try:
                sf = shapefile.Reader(shp_path)
                fields = [f[0] for f in sf.fields[1:]] # Skip DeletionFlag
                
                # Intentamos identificar qué campo usar para el nombre si no existe name_attribute
                actual_name_attr = name_attribute if name_attribute in fields else fields[0] if fields else 'Unknown'
                
                for sr in sf.shapeRecords():
                    # Get GeoJSON geometry dict
                    geom = sr.shape.__geo_interface__
                    
                    record_dict = sr.record.as_dict()
                    route_name = str(record_dict.get(actual_name_attr, f'Ruta {created_count}'))
                    
                    # Convert geom to json string
                    geojson_str = json.dumps(geom)
                    
                    # Verificar si existe
                    existing = Route.search([('name', '=', route_name)], limit=1)
                    if existing:
                        existing.write({
                            'geojson': geojson_str,
                            'business_unit': business_unit or existing.business_unit
                        })
                    else:
                        Route.create({
                            'name': route_name,
                            'geojson': geojson_str,
                            'business_unit': business_unit
                        })
                    created_count += 1
            except Exception as e:
                _logger.error("Error al procesar %s: %s", filename, str(e))
                
    _logger.info("Importación de shapefiles finalizada. %s rutas creadas/actualizadas.", created_count)
    return created_count
