import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from odoo import api, fields, SUPERUSER_ID

# Configuración del Logger para escribir en el archivo dedicado
LOG_DIR = os.path.expanduser('~/odoo_import_logs') if os.name == 'posix' else 'C:\\odoo_import_logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_file_path = os.path.join(LOG_DIR, 'excel_importer.log')

# Configurar el logging
logger = logging.getLogger('block_routes.excel_importer')
logger.setLevel(logging.INFO)

# Evitar duplicación de handlers si ya se ha importado
if not logger.handlers:
    fh = logging.FileHandler(log_file_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    # También añadir handler de consola para depuración
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def import_excel_blocked_routes(env, directory_path='data/rutasBloqueadas'):
    """
    Lee archivos Excel (.xlsx) desde un directorio específico y registra bloqueos en block_routes.blocked.
    
    Reglas:
    - La fila 10 es el encabezado (0-indexed en pandas es row 9).
    - Las columnas a concatenar para identificar la ruta son: PROV, CAN, SEC, RUTA.
    - Fecha inicio = 'FECHA GENERACIÓN ÓRDENES DE LECTURA' - 7 días.
    - Fecha fin = 'BATCH:                 *EMISIÓN DE FACTURAS *ENVIO AL SRI (1) *MAQUETACIÓN PDF'.
    - Conversión y validación de tipos rigurosa.
    - Registra logs detallados de la importación y errores en un archivo físico.
    """
    logger.info("========================================= INICIANDO IMPORTACIÓN DE EXCEL =========================================")
    
    # Determinar ruta absoluta de búsqueda
    full_path = os.path.join(env.cr.dbname, directory_path)
    import odoo.modules
    module_path = odoo.modules.get_module_path('blockRoutes')
    if module_path:
        full_path = os.path.join(module_path, directory_path)
        
    if not os.path.exists(full_path):
        logger.error(f"El directorio especificado no existe: {full_path}")
        return False
        
    excel_files = [f for f in os.listdir(full_path) if f.endswith(('.xlsx', '.xls'))]
    if not excel_files:
        logger.warning(f"No se encontraron archivos Excel en la ruta: {full_path}")
        return False
        
    Route = env['block_routes.route']
    Blocked = env['block_routes.blocked']
    
    total_records_processed = 0
    total_blocked_created = 0
    
    for filename in excel_files:
        file_path = os.path.join(full_path, filename)
        logger.info(f"Procesando archivo: {filename}")
        
        try:
            # Leer Excel indicando tipos string para las columnas de la clave de ruta para conservar ceros a la izquierda
            df = pd.read_excel(
                file_path, 
                header=9,
                dtype={
                    'PROV': str,
                    'CAN': str,
                    'SECT': str,
                    'RUTA': str
                }
            )
        except Exception as e:
            logger.error(f"Error crítico al leer el archivo Excel {filename}: {str(e)}")
            continue
            
        # Limpiar espacios en los nombres de las columnas para evitar problemas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Verificar la existencia de las columnas obligatorias
        required_cols = [
            'PROV', 'CAN', 'SECT', 'RUTA', 
            'FECHA GENERACIÓN ÓRDENES DE LECTURA',
            'BATCH:                 *EMISIÓN DE FACTURAS *ENVIO AL SRI (1) *MAQUETACIÓN PDF'
        ]
        
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"El archivo {filename} no contiene las columnas necesarias: {missing_cols}. Columnas encontradas: {list(df.columns)}")
            continue
            
        logger.info(f"Columnas detectadas correctamente. Procediendo a procesar {len(df)} filas...")
        
        for idx, row in df.iterrows():
            row_num = idx + 11  # Fila real de Excel (índice 0 en df es fila 11 en Excel al tener cabecera en fila 10)
            
            # 1. Obtener valores y comprobar si la fila está vacía
            prov_val = row.get('PROV')
            can_val = row.get('CAN')
            sec_val = row.get('SECT')
            ruta_val = row.get('RUTA')
            
            # Ignorar filas completamente vacías
            if pd.isna(prov_val) and pd.isna(can_val) and pd.isna(sec_val) and pd.isna(ruta_val):
                continue
                
            total_records_processed += 1
            
            # 2. Concatenación segura y con relleno de ceros a la izquierda de la clave de ruta (PROV + CAN + SECT + RUTA)
            def sanitize_code(val, pad_length):
                if pd.isna(val):
                    return "0" * pad_length
                
                # Convertimos a string y removemos espacios
                s = str(val).strip()
                
                # Eliminar decimales si es flotante en string (ej: '7.0')
                if s.endswith('.0'):
                    s = s[:-2]
                    
                if not s or s.lower() in ('nan', 'null', 'none'):
                    return "0" * pad_length
                    
                # Rellenar con ceros a la izquierda para garantizar el formato (ej: '7' -> '07')
                return s.zfill(pad_length)
                
            prov_str = sanitize_code(prov_val, 2)
            can_str = sanitize_code(can_val, 2)
            sec_str = sanitize_code(sec_val, 2)
            ruta_str = sanitize_code(ruta_val, 3)
            
            if not (prov_str or can_str or sec_str or ruta_str):
                logger.warning(f"Fila {row_num}: Saltando registro porque todos los campos de clave están vacíos.")
                continue
                
            # Concatenamos para formar el ID de ruta
            route_id_str = f"{prov_str}{can_str}{sec_str}{ruta_str}"
            
            if not route_id_str:
                logger.warning(f"Fila {row_num}: Clave de ruta concatenada vacía.")
                continue
                
            # 3. Buscar la ruta correspondiente en Odoo
            route_rec = Route.search([('name', '=', route_id_str)], limit=1)
            if not route_rec:
                logger.warning(f"Fila {row_num}: No existe la ruta '{route_id_str}' registrada en el mapa de Odoo. Se omite el bloqueo.")
                continue
                
            # 4. Procesar y convertir fechas
            raw_start_date = row.get('FECHA GENERACIÓN ÓRDENES DE LECTURA')
            raw_end_date = row.get('BATCH:                 *EMISIÓN DE FACTURAS *ENVIO AL SRI (1) *MAQUETACIÓN PDF')
            
            if pd.isna(raw_start_date) or pd.isna(raw_end_date):
                logger.warning(f"Fila {row_num}: Fechas incompletas para la ruta '{route_id_str}'. Start: {raw_start_date}, End: {raw_end_date}")
                continue
                
            # Función auxiliar para convertir valores de celdas a DateTime
            def parse_date(date_val):
                if isinstance(date_val, (datetime, pd.Timestamp)):
                    return date_val.to_pydatetime() if hasattr(date_val, 'to_pydatetime') else date_val
                elif isinstance(date_val, str):
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y'):
                        try:
                            return datetime.strptime(date_val.strip(), fmt)
                        except ValueError:
                            continue
                return None
                
            start_date_parsed = parse_date(raw_start_date)
            end_date_parsed = parse_date(raw_end_date)
            
            if not start_date_parsed or not end_date_parsed:
                logger.error(f"Fila {row_num}: Error al parsear fechas para la ruta '{route_id_str}'. Formatos ilegibles. Start: {raw_start_date}, End: {raw_end_date}")
                continue
                
            # Aplicar regla: Fecha de bloqueo empieza 7 días antes de la Fecha de Generación de Lectura
            date_start_final = start_date_parsed - timedelta(days=7)
            date_end_final = end_date_parsed
            
            if date_end_final <= date_start_final:
                logger.warning(f"Fila {row_num}: Fecha de fin ({date_end_final}) es anterior o igual a la de inicio ({date_start_final}) para la ruta '{route_id_str}'. Ajustando...")
                continue
                
            # 5. Registrar el Bloqueo en la Base de Datos
            try:
                # Comprobar si ya existe un registro idéntico de bloqueo activo para evitar duplicados en la misma ruta en el mismo periodo
                existing_block = Blocked.search([
                    ('route_id', '=', route_rec.id),
                    ('date_start', '=', date_start_final),
                    ('date_end', '=', date_end_final)
                ], limit=1)
                
                if existing_block:
                    logger.info(f"Fila {row_num}: El bloqueo para la ruta '{route_id_str}' ({date_start_final} - {date_end_final}) ya existe. Saltando creación.")
                    continue
                    
                Blocked.create({
                    'route_id': route_rec.id,
                    'reason': f"Bloqueo automático según Cronograma de Lectura y Facturación. Periodo de lectura del {start_date_parsed.strftime('%Y-%m-%d')}.",
                    'date_start': date_start_final,
                    'date_end': date_end_final
                })
                total_blocked_created += 1
                logger.info(f"Fila {row_num}: Registrado bloqueo exitoso para la ruta '{route_id_str}' ({date_start_final.strftime('%Y-%m-%d %H:%M:%S')} al {date_end_final.strftime('%Y-%m-%d %H:%M:%S')})")
                
            except Exception as e:
                logger.error(f"Fila {row_num}: Error al insertar bloqueo en la base de datos de Odoo: {str(e)}")
                
    logger.info(f"================ IMPORTACIÓN DE EXCEL FINALIZADA. Procesados: {total_records_processed} registros. Bloqueos creados: {total_blocked_created} =================\n")
    return total_blocked_created
