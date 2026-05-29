import os
import json
import logging
import math
from odoo import api, SUPERUSER_ID

# Configuración del Logger para escribir en el archivo dedicado
LOG_DIR = os.path.expanduser('~/odoo_import_logs') if os.name == 'posix' else 'C:\\odoo_import_logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_file_path = os.path.join(LOG_DIR, 'shape_importer.log')

# Configurar el logging
_logger = logging.getLogger('block_routes.shape_importer')
_logger.setLevel(logging.INFO)

if not _logger.handlers:
    fh = logging.FileHandler(log_file_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    _logger.addHandler(fh)
    # También añadir handler de consola
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    _logger.addHandler(ch)

try:
    import shapefile
except ImportError:
    shapefile = None
    _logger.warning("Libreria 'pyshp' no está instalada. Ejecute 'pip install pyshp' para importar shapefiles.")

def psad56_to_wgs84_molodensky(lat, lon):
    """
    Transformación de Molodensky de 3 parámetros para convertir Lat/Lng
    del Datum PSAD56 (Internacional 1924) a WGS84 en Ecuador.
    Utiliza los parámetros oficiales calibrados por el IGM (Instituto Geográfico Militar de Ecuador)
    para eliminar desplazamientos locales viales.
    """
    try:
        phi = lat * math.pi / 180.0
        lam = lon * math.pi / 180.0
        
        # Parámetros Elipsoide PSAD56 (Internacional 1924 / Hayford)
        a = 6378388.0
        f = 1.0 / 297.0
        
        # Parámetros Elipsoide WGS84
        a_wgs = 6378137.0
        f_wgs = 1.0 / 298.257223563
        
        da = a_wgs - a      # -251.0
        df = f_wgs - f      # -1.4192702248556637e-05
        
        # Parámetros de desplazamiento oficiales del IGM Ecuador (PSAD56 -> SIRGAS/WGS84)
        # Ofrecen una precisión local muy superior a los parámetros globales de Sudamérica.
        dx = -60.310
        dy = 245.935
        dz = 31.008
        
        sin_phi = math.sin(phi)
        cos_phi = math.cos(phi)
        sin_lam = math.sin(lam)
        cos_lam = math.cos(lam)
        
        # Primera excentricidad al cuadrado para PSAD56
        e2 = 2.0 * f - f**2
        
        # Radio de curvatura vertical primaria (N) y meridional (M)
        N = a / math.sqrt(1.0 - e2 * sin_phi**2)
        M = a * (1.0 - e2) / (1.0 - e2 * sin_phi**2)**1.5
        
        # Fórmula de Molodensky para el desplazamiento
        dphi = (-dx * sin_phi * cos_lam - dy * sin_phi * sin_lam + dz * cos_phi + 
                (a * df + f * da) * math.sin(2.0 * phi)) / M
                
        dlam = (-dx * sin_lam + dy * cos_lam) / (N * cos_phi)
        
        # Aplicar el desplazamiento y convertir de radianes a grados
        lat_wgs = lat + dphi * 180.0 / math.pi
        lon_wgs = lon + dlam * 180.0 / math.pi
        
        return lat_wgs, lon_wgs
    except Exception as e:
        _logger.warning("Error en conversión de Molodensky: %s", str(e))
        return lat, lon

def utm_17s_to_wgs84(easting, northing):
    """
    Convierte coordenadas UTM Zona 17 Sur a WGS84 (latitud, longitud).
    Calcula inicialmente sobre el elipsoide Hayford (Internacional 1924) para PSAD56
    y luego aplica la transformación oficial Molodensky del IGM Ecuador.
    """
    try:
        # Constantes del Elipsoide Internacional 1924 (PSAD56)
        a = 6378388.0         # Radio ecuatorial (semi-major axis)
        f = 1.0 / 297.0       # Aplanamiento (flattening)
        b = a * (1.0 - f)     # Radio polar (semi-minor axis)
        
        # Parámetros UTM
        k0 = 0.9996           # Factor de escala en el meridiano central
        e = math.sqrt(1.0 - (b/a)**2) # Primera excentricidad
        e2 = e**2 / (1.0 - e**2)
        
        x = easting - 500000.0 # Desplazamiento respecto al meridiano central (500k)
        y = northing - 10000000.0 # Hemisferio Sur: Restamos 10,000,000 m
        
        # Parámetros del arco meridiano
        mu = y / (a * (1.0 - e**2 / 4.0 - 3.0 * e**4 / 64.0 - 5.0 * e**6 / 256.0))
        
        # Latitud de huella (footprint latitude)
        e1 = (1.0 - math.sqrt(1.0 - e**2)) / (1.0 + math.sqrt(1.0 - e**2))
        J1 = (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0)
        J2 = (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0)
        J3 = (151.0 * e1**3 / 96.0)
        J4 = (1097.0 * e1**4 / 512.0)
        
        fp = mu + J1 * math.sin(2.0*mu) + J2 * math.sin(4.0*mu) + J3 * math.sin(6.0*mu) + J4 * math.sin(8.0*mu)
        
        # Parámetros de curvatura en latitud de huella
        C1 = e2 * math.cos(fp)**2
        T1 = math.tan(fp)**2
        R1 = a * (1.0 - e**2) / (1.0 - e**2 * math.sin(fp)**2)**1.5
        N1 = a / math.sqrt(1.0 - e**2 * math.sin(fp)**2)
        D = x / (N1 * k0)
        
        # Cálculo de Latitud PSAD56
        lat = fp - (N1 * math.tan(fp) / R1) * (
            D**2 / 2.0 - 
            (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1**2 - 9.0 * e2) * D**4 / 24.0 +
            (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1**2 - 252.0 * e2 - 3.0 * C1**2) * D**6 / 720.0
        )
        
        # Cálculo de Longitud PSAD56 (Meridiano Central Zona 17 = -81.0 grados)
        lon0 = -81.0 * math.pi / 180.0
        
        cos_fp = math.cos(fp)
        if abs(cos_fp) < 1e-9:
            return None, None
            
        lon = lon0 + (
            D - 
            (1.0 + 2.0 * T1 + C1) * D**3 / 6.0 + 
            (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1**2 + 8.0 * e2 + 24.0 * T1**2) * D**5 / 120.0
        ) / cos_fp
        
        # Convertir radianes a grados
        lat = lat * 180.0 / math.pi
        lon = lon * 180.0 / math.pi
        
        # APLICAR TRANSFORMACIÓN DE MOLODENSKY A WGS84 (IGM ECUADOR)
        lat_wgs, lon_wgs = psad56_to_wgs84_molodensky(lat, lon)
        
        return lat_wgs, lon_wgs
    except (ValueError, OverflowError, ZeroDivisionError) as err:
        _logger.warning("Fallo en conversión UTM para coordenadas (%s, %s): %s", easting, northing, str(err))
        return None, None

def reproject_geom_coords(coords, geom_type, lat_offset=0.0, lon_offset=0.0):
    """
    Reproyecta recursivamente las coordenadas de una geometría GeoJSON
    de UTM Zona 17 Sur a WGS84 Lat/Lng, aplicando además los offsets de calibración.
    """
    if geom_type == 'Point':
        if len(coords) >= 2:
            lat, lon = utm_17s_to_wgs84(coords[0], coords[1])
            if lat is not None and lon is not None:
                return [lon + lon_offset, lat + lat_offset]
            return coords
    elif geom_type in ('LineString', 'MultiPoint'):
        new_coords = []
        for pt in coords:
            lat, lon = utm_17s_to_wgs84(pt[0], pt[1])
            if lat is not None and lon is not None:
                new_coords.append([lon + lon_offset, lat + lat_offset])
            else:
                new_coords.append(pt)
        return new_coords
    elif geom_type in ('Polygon', 'MultiLineString'):
        new_coords = []
        for ring in coords:
            new_ring = []
            for pt in ring:
                lat, lon = utm_17s_to_wgs84(pt[0], pt[1])
                if lat is not None and lon is not None:
                    new_ring.append([lon + lon_offset, lat + lat_offset])
                else:
                    new_ring.append(pt)
            new_coords.append(new_ring)
        return new_coords
    elif geom_type == 'MultiPolygon':
        new_coords = []
        for poly in coords:
            new_poly = []
            for ring in poly:
                new_ring = []
                for pt in ring:
                    lat, lon = utm_17s_to_wgs84(pt[0], pt[1])
                    if lat is not None and lon is not None:
                        new_ring.append([lon + lon_offset, lat + lat_offset])
                    else:
                        new_ring.append(pt)
                new_poly.append(new_ring)
            new_coords.append(new_poly)
        return new_coords
    return coords

def point_in_polygon(x, y, shape):
    """
    Verifica si un punto (x, y) está dentro del polígono del shapefile.
    Soporta polígonos multiparte (islas/anillos).
    """
    points = shape.points
    parts = list(shape.parts) + [len(points)]
    
    inside = False
    for idx in range(len(parts) - 1):
        start = parts[idx]
        end = parts[idx + 1]
        ring = points[start:end]
        
        n = len(ring)
        if n < 3:
            continue
        ring_inside = False
        p1x, p1y = ring[0]
        for i in range(n + 1):
            p2x, p2y = ring[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            ring_inside = not ring_inside
            p1x, p1y = p2x, p2y
        
        if ring_inside:
            inside = not inside
            
    return inside

def import_shapes_to_routes(env, directory_path='data/shapes/', business_unit=False):
    """
    Lee dos archivos Shapefile desde un directorio:
    - Uno que contenga 'secuencia' o 'sequence' (puntos de secuencia de lectura).
    - Otro que contenga 'ruta' o 'route' (polígonos de rutas).
    Relaciona espacialmente cada polígono con sus secuencias internas
    y extrae el identificador único (CANCOD + SICOSEC + SICORUT).
    
    Detecta automáticamente si el archivo está en proyección UTM Zona 17 Sur (en metros)
    y lo reproyecta matemáticamente a coordenadas geográficas WGS84 (Lat/Lng) exigidas por Leaflet.
    Aplica la transformación geodésica de Molodensky del IGM Ecuador.
    Permite además calibrar milimétricamente el mapa configurando offsets en Parámetros del Sistema de Odoo:
      * 'block_routes.latitude_offset'
      * 'block_routes.longitude_offset'
    """
    if not shapefile:
        _logger.error("No se puede importar: pyshp no está instalado.")
        return False
        
    full_path = os.path.join(env.cr.dbname, directory_path)
    import odoo.modules
    module_path = odoo.modules.get_module_path('blockRoutes')
    if module_path:
        full_path = os.path.join(module_path, directory_path)
        
    if not os.path.exists(full_path):
        _logger.error("El directorio de shapefiles no existe: %s", full_path)
        return False
        
    # OBTENER PARÁMETROS DE CALIBRACIÓN MANUAL DESDE ODOO (Por si persiste algún micro-desfase del Shapefile original)
    icp = env['ir.config_parameter'].sudo()
    try:
        lat_offset = float(icp.get_param('block_routes.latitude_offset', default='0.0'))
        lon_offset = float(icp.get_param('block_routes.longitude_offset', default='0.0'))
    except Exception:
        _logger.warning("Los parámetros de offset de blockRoutes no son números válidos. Usando 0.0.")
        lat_offset = 0.0
        lon_offset = 0.0
        
    if lat_offset != 0.0 or lon_offset != 0.0:
        _logger.info("Aplicando calibración manual de offsets durante la importación: Lat: %s, Lon: %s", lat_offset, lon_offset)
        
    # Identificar los archivos
    ruta_shp_path = None
    secuencia_shp_path = None
    
    for filename in os.listdir(full_path):
        if filename.endswith(".shp"):
            lower_name = filename.lower()
            if "secuencia" in lower_name or "sequence" in lower_name:
                secuencia_shp_path = os.path.join(full_path, filename)
            elif "ruta" in lower_name or "route" in lower_name:
                ruta_shp_path = os.path.join(full_path, filename)
                
    if not ruta_shp_path:
        _logger.error("No se encontró ningún Shapefile de Rutas (que contenga 'ruta' o 'route' en el nombre) en %s", full_path)
        return False
        
    if not secuencia_shp_path:
        _logger.error("No se encontró ningún Shapefile de Secuencias (que contenga 'secuencia' o 'sequence' en el nombre) en %s", full_path)
        return False
        
    _logger.info("Iniciando lectura de Secuencias desde: %s", secuencia_shp_path)
    sequence_points = []
    try:
        sf_seq = shapefile.Reader(secuencia_shp_path)
        for sr in sf_seq.shapeRecords():
            geom = sr.shape.__geo_interface__
            coords = geom.get('coordinates')
            
            # Extraer punto [x, y]
            x, y = None, None
            if geom.get('type') == 'Point' and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                x, y = coords[0], coords[1]
            elif isinstance(coords, (list, tuple)) and len(coords) > 0:
                first = coords[0]
                if isinstance(first, (list, tuple)) and len(first) >= 2:
                    x, y = first[0], first[1]
                    
            if x is None or y is None:
                continue
                
            # AUTO-DETECCIÓN Y REPROYECCIÓN DE UTM A WGS84
            if x > 180 or x < -180 or y > 90 or y < -90:
                lat, lon = utm_17s_to_wgs84(x, y)
                if lat is None or lon is None:
                    continue
                # Aplicamos la calibración
                x, y = lon + lon_offset, lat + lat_offset
            else:
                # Ya está en WGS84, solo aplicamos calibración opcional
                x, y = x + lon_offset, y + lat_offset
                
            rec = sr.record.as_dict()
            cancod = str(rec.get('CANCOD', '')).strip()
            sicosec = str(rec.get('SICOSEC', '')).strip()
            sicorut = str(rec.get('SICORUT', '')).strip()
            
            # Concatenar campos como identificador único
            route_id = f"{cancod}{sicosec}{sicorut}"
            if not route_id or route_id.strip() == "":
                route_id = str(rec.get('AGERUT', '')).strip()
                
            if route_id:
                sequence_points.append({
                    'x': x,
                    'y': y,
                    'route_id': route_id
                })
        _logger.info("Se cargaron %s puntos de secuencia con identificadores válidos.", len(sequence_points))
    except Exception as e:
        _logger.error("Error al procesar el archivo de Secuencias: %s", str(e))
        return False
        
    _logger.info("Iniciando lectura de Rutas desde: %s", ruta_shp_path)
    Route = env['block_routes.route']
    created_count = 0
    
    try:
        sf_route = shapefile.Reader(ruta_shp_path)
        for sr in sf_route.shapeRecords():
            geom = sr.shape.__geo_interface__
            shape = sr.shape
            if not shape.points:
                continue
                
            # AUTO-DETECCIÓN Y REPROYECCIÓN DE POLÍGONO UTM A WGS84
            first_x = shape.points[0][0]
            first_y = shape.points[0][1]
            is_utm = (first_x > 180 or first_x < -180 or first_y > 90 or first_y < -90)
            
            # Crear polígonos para PIP y GeoJSON re-proyectados si es necesario
            poly_points = []
            if is_utm:
                # Reproyectamos la geometría completa para el GeoJSON y aplicamos offsets
                geom['coordinates'] = reproject_geom_coords(geom['coordinates'], geom['type'], lat_offset, lon_offset)
                # Reproyectamos el array de puntos planos para el Point-in-Polygon
                for pt in shape.points:
                    lat, lon = utm_17s_to_wgs84(pt[0], pt[1])
                    if lat is not None and lon is not None:
                        poly_points.append((lon + lon_offset, lat + lat_offset))
                    else:
                        poly_points.append((pt[0] + lon_offset, pt[1] + lat_offset)) # Fallback
            else:
                poly_points = [(pt[0] + lon_offset, pt[1] + lat_offset) for pt in shape.points]
                # Aplicamos offsets también al GeoJSON WGS84
                geom['coordinates'] = reproject_geom_coords(geom['coordinates'], geom['type'], lat_offset, lon_offset)
                
            geojson_str = json.dumps(geom)
            
            # Crear un objeto temporal que tenga los puntos WGS84 para PIP
            class TempShape:
                def __init__(self, points, parts):
                    self.points = points
                    self.parts = parts
            
            temp_wgs84_shape = TempShape(poly_points, shape.parts)
            
            # Determinar el identificador único mediante Point-in-Polygon
            matched_route_id = None
            for sp in sequence_points:
                if point_in_polygon(sp['x'], sp['y'], temp_wgs84_shape):
                    matched_route_id = sp['route_id']
                    break
                    
            if not matched_route_id:
                # Si no se encuentra secuencia dentro, generamos uno por defecto
                matched_route_id = f"Ruta_Desconocida_{created_count}"
                
            # Crear o actualizar en Odoo
            existing = Route.search([('name', '=', matched_route_id)], limit=1)
            if existing:
                existing.write({
                    'geojson': geojson_str,
                    'business_unit': business_unit or existing.business_unit
                })
            else:
                Route.create({
                    'name': matched_route_id,
                    'geojson': geojson_str,
                    'business_unit': business_unit
                })
            created_count += 1
    except Exception as e:
        _logger.error("Error al procesar el archivo de Rutas: %s", str(e))
        return False
        
    _logger.info("Importación de shapefiles finalizada exitosamente. %s rutas registradas.", created_count)
    return created_count
