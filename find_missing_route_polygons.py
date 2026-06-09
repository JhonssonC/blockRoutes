import os
import json
import math
import shapefile

def psad56_to_wgs84_molodensky(lat, lon):
    try:
        phi = lat * math.pi / 180.0
        lam = lon * math.pi / 180.0
        
        a = 6378388.0
        f = 1.0 / 297.0
        
        a_wgs = 6378137.0
        f_wgs = 1.0 / 298.257223563
        
        da = a_wgs - a
        df = f_wgs - f
        
        dx = -60.310
        dy = 245.935
        dz = 31.008
        
        sin_phi = math.sin(phi)
        cos_phi = math.cos(phi)
        sin_lam = math.sin(lam)
        cos_lam = math.cos(lam)
        
        e2 = 2.0 * f - f**2
        N = a / math.sqrt(1.0 - e2 * sin_phi**2)
        M = a * (1.0 - e2) / (1.0 - e2 * sin_phi**2)**1.5
        
        dphi = (-dx * sin_phi * cos_lam - dy * sin_phi * sin_lam + dz * cos_phi + 
                (a * df + f * da) * math.sin(2.0 * phi)) / M
                
        dlam = (-dx * sin_lam + dy * cos_lam) / (N * cos_phi)
        
        lat_wgs = lat + dphi * 180.0 / math.pi
        lon_wgs = lon + dlam * 180.0 / math.pi
        
        return lat_wgs, lon_wgs
    except Exception:
        return lat, lon

def utm_17s_to_wgs84(easting, northing):
    try:
        a = 6378388.0
        f = 1.0 / 297.0
        b = a * (1.0 - f)
        
        k0 = 0.9996
        e = math.sqrt(1.0 - (b/a)**2)
        e2 = e**2 / (1.0 - e**2)
        
        x = easting - 500000.0
        y = northing - 10000000.0
        
        mu = y / (a * (1.0 - e**2 / 4.0 - 3.0 * e**4 / 64.0 - 5.0 * e**6 / 256.0))
        
        e1 = (1.0 - math.sqrt(1.0 - e**2)) / (1.0 + math.sqrt(1.0 - e**2))
        J1 = (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0)
        J2 = (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0)
        J3 = (151.0 * e1**3 / 96.0)
        J4 = (1097.0 * e1**4 / 512.0)
        
        fp = mu + J1 * math.sin(2.0*mu) + J2 * math.sin(4.0*mu) + J3 * math.sin(6.0*mu) + J4 * math.sin(8.0*mu)
        
        C1 = e2 * math.cos(fp)**2
        T1 = math.tan(fp)**2
        R1 = a * (1.0 - e**2) / (1.0 - e**2 * math.sin(fp)**2)**1.5
        N1 = a / math.sqrt(1.0 - e**2 * math.sin(fp)**2)
        D = x / (N1 * k0)
        
        lat = fp - (N1 * math.tan(fp) / R1) * (
            D**2 / 2.0 - 
            (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1**2 - 9.0 * e2) * D**4 / 24.0 +
            (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1**2 - 252.0 * e2 - 3.0 * C1**2) * D**6 / 720.0
        )
        
        lon0 = -81.0 * math.pi / 180.0
        cos_fp = math.cos(fp)
        if abs(cos_fp) < 1e-9:
            return None, None
            
        lon = lon0 + (
            D - 
            (1.0 + 2.0 * T1 + C1) * D**3 / 6.0 + 
            (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1**2 + 8.0 * e2 + 24.0 * T1**2) * D**5 / 120.0
        ) / cos_fp
        
        lat = lat * 180.0 / math.pi
        lon = lon * 180.0 / math.pi
        
        lat_wgs, lon_wgs = psad56_to_wgs84_molodensky(lat, lon)
        return lat_wgs, lon_wgs
    except Exception:
        return None, None

def point_in_polygon(x, y, shape_points, shape_parts, bbox):
    if not (bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]):
        return False
        
    parts = list(shape_parts) + [len(shape_points)]
    inside = False
    for idx in range(len(parts) - 1):
        start = parts[idx]
        end = parts[idx + 1]
        ring = shape_points[start:end]
        
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

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    shp_dir = os.path.join(base_dir, "data", "shapes")
    
    ruta_shp = os.path.join(shp_dir, "Ruta.shp")
    sec_shp = os.path.join(shp_dir, "Secuencia.shp")
    
    # Load mapping
    mapping_path = os.path.join(base_dir, "tools", "route_mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path, "r", encoding="utf-8") as f:
            route_mapping = json.load(f)
    else:
        route_mapping = {}
        
    # Get all sequence points route IDs
    print("Loading sequences...")
    sf_seq = shapefile.Reader(sec_shp)
    seq_routes = set()
    for rec in sf_seq.records():
        d = rec.as_dict()
        cancod = str(d.get('CANCOD', '')).strip()
        sicosec = str(d.get('SICOSEC', '')).strip()
        sicorut = str(d.get('SICORUT', '')).strip()
        route_id = f"{cancod}{sicosec}{sicorut}"
        if not route_id or route_id.strip() == "":
            route_id = str(d.get('AGERUT', '')).strip()
        if route_id:
            seq_routes.add(route_id)
            
    print(f"Total unique route IDs in Secuencia.shp: {len(seq_routes)}")
    
    # Get all route IDs from Ruta.shp (either matched by PIP or resolved in mapping)
    print("Loading routes...")
    sf_route = shapefile.Reader(ruta_shp)
    route_polys = []
    
    # Load sequence points coordinates for PIP
    sequence_points = []
    sf_seq_reader = shapefile.Reader(sec_shp)
    for sr in sf_seq_reader.shapeRecords():
        geom = sr.shape.__geo_interface__
        coords = geom.get('coordinates')
        x, y = None, None
        if geom.get('type') == 'Point' and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            x, y = coords[0], coords[1]
        elif isinstance(coords, (list, tuple)) and len(coords) > 0:
            first = coords[0]
            if isinstance(first, (list, tuple)) and len(first) >= 2:
                x, y = first[0], first[1]
                
        if x is None or y is None:
            continue
            
        if x > 180 or x < -180 or y > 90 or y < -90:
            lat, lon = utm_17s_to_wgs84(x, y)
            if lat is not None and lon is not None:
                x, y = lon, lat
                
        d = sr.record.as_dict()
        cancod = str(d.get('CANCOD', '')).strip()
        sicosec = str(d.get('SICOSEC', '')).strip()
        sicorut = str(d.get('SICORUT', '')).strip()
        route_id = f"{cancod}{sicosec}{sicorut}"
        if not route_id or route_id.strip() == "":
            route_id = str(d.get('AGERUT', '')).strip()
        if route_id:
            sequence_points.append({'x': x, 'y': y, 'route_id': route_id})
            
    polygon_routes = set()
    for idx, sr in enumerate(sf_route.shapeRecords()):
        rec = sr.record.as_dict()
        globalid = rec.get('GLOBALID')
        
        # Check if resolved in mapping
        if globalid in route_mapping:
            polygon_routes.add(route_mapping[globalid])
            continue
            
        # Run PIP
        shape = sr.shape
        if not shape.points:
            continue
        first_x = shape.points[0][0]
        first_y = shape.points[0][1]
        is_utm = (first_x > 180 or first_x < -180 or first_y > 90 or first_y < -90)
        
        poly_points = []
        for pt in shape.points:
            if is_utm:
                lat, lon = utm_17s_to_wgs84(pt[0], pt[1])
                if lat is not None and lon is not None:
                    poly_points.append((lon, lat))
            else:
                poly_points.append((pt[0], pt[1]))
                
        if not poly_points:
            continue
            
        xs = [pt[0] for pt in poly_points]
        ys = [pt[1] for pt in poly_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        bbox = (min_x, min_y, max_x, max_y)
        
        matched_route_id = None
        for sp in sequence_points:
            if point_in_polygon(sp['x'], sp['y'], poly_points, shape.parts, bbox):
                matched_route_id = sp['route_id']
                break
                
        if matched_route_id:
            polygon_routes.add(matched_route_id)
            
    print(f"Total unique route IDs matched/mapped to polygons in Ruta.shp: {len(polygon_routes)}")
    
    missing_polygons = seq_routes - polygon_routes
    print(f"Route IDs in Secuencia.shp that have NO polygon in Ruta.shp: {len(missing_polygons)}")
    if missing_polygons:
        print("Sample missing route IDs (first 20):")
        for r in sorted(list(missing_polygons))[:20]:
            print(f" - {r}")

if __name__ == "__main__":
    main()
