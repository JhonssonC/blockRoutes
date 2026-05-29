# Blocked Routes Map Viewer (`blockRoutes`)

Módulo avanzado de **Odoo 18** diseñado para el **Visor de Rutas de Ecuador** y la gestión espacializada de **rutas bloqueadas**. Este módulo automatiza la importación de datos cartográficos (Shapefiles) y calendarios de lecturas/emisiones (archivos Excel de facturación), previniendo que unidades de atencion levanten actividades a ejecutar en sectores bloqueados gracias a un mapa interactivo con geolocalización en tiempo real.

---

## 🚀 Características Principales

* **🗺️ Visor de Mapas Interactivo (OWL + Leaflet):**
  * Renderización de polígonos de rutas en la interfaz backend utilizando Leaflet.
  * Código de colores intuitivo: **Azul** para vías libres y **Rojo** para rutas con bloqueos activos.
  * **Geolocalización en tiempo real:** Rastrea la posición del operario en campo y le advierte visualmente si ingresa físicamente dentro del polígono de una ruta bloqueada.
* **🌐 Importador Espacial de Shapefiles (`shape_importer`):**
  * Carga y procesa archivos Shapefile de polígonos de rutas y puntos de secuencia de lectura.
  * **Auto-reproyección:** Detecta si el mapa está en proyección local **UTM Zona 17 Sur (PSAD56)** y realiza la conversión geodésica matemática a coordenadas geográficas **WGS84 (Lat/Lng)**.
  * **Calibración Molodensky (IGM Ecuador):** Aplica la transformación oficial de Molodensky de 3 parámetros calibrada por el Instituto Geográfico Militar de Ecuador para eliminar micro-desplazamientos cartográficos locales.
  * Relación espacial automatizada mediante análisis **Point-In-Polygon (PIP)** para emparejar polígonos con sus secuencias.
* **📊 Importador Inteligente de Cronogramas Excel (`excel_importer`):**
  * Procesa de forma masiva los archivos de Excel del cronograma de lecturas.
  * **Formateo de Claves de 9 Dígitos:** Lee y concatena las columnas de clave (`PROV` + `CAN` + `SECT` + `RUTA`) forzando el formato texto y rellenando con ceros a la izquierda (evitando la pérdida de ceros iniciales como `07` o `025` ocasionada por el auto-casteo numérico habitual de Excel).
  * **Cálculo de Vigencia de Bloqueos:** 
    * Fecha de inicio = `FECHA GENERACIÓN ÓRDENES DE LECTURA` menos **7 días de gracia**.
    * Fecha de fin = Columna de batch de facturación/emisión.
* **⏱️ Automatización mediante Crons Nativos:**
  * Dos **Acciones Planificadas** de Odoo configuradas para ejecutarse **diariamente de forma automática** para escanear y volcar nuevos datos.
* **📂 Historial de Logs Físicos Dedicados:**
  * Almacenamiento local de auditoría en la carpeta `odoo_import_logs` en el servidor (soporta Windows y entornos Linux/Docker).

---

## 📂 Estructura de Directorios Clave

```text
blockRoutes/
├── data/
│   ├── ir_cron_data.xml         # Declaración de las acciones planificadas diarias
│   ├── rutasBloqueadas/         # Ubicación de archivos Excel del Cronograma (*.xlsx) [Ignorado por Git]
│   └── shapes/                  # Ubicación de archivos Shapefile (*.shp, *.dbf, etc.) [Ignorado por Git]
├── models/
│   ├── blocked_route.py         # Modelo 'block_routes.blocked' y métodos de Crons
│   └── route.py                 # Modelo 'block_routes.route' (geometrías en GeoJSON)
├── security/
│   ├── ir.model.access.csv      # Permisos de acceso del sistema
│   └── security.xml             # Reglas de registro y grupos de usuarios
├── static/
│   └── src/
│       ├── css/map_view.css     # Estilos del mapa y la superposición de datos
│       ├── js/map_view.js       # Componente OWL de Leaflet y geolocalización en tiempo real
│       └── xml/map_view.xml     # Plantilla XML del visor OWL
├── tools/
│   ├── excel_importer.py        # Algoritmos de importación, parseo de texto y logs de Excel
│   └── shape_importer.py        # Algoritmo de reproyección UTM-WGS84 y Point-In-Polygon
└── wizard/
    └── blocked_route_import_wizard.py  # Asistente manual de subida rápida de Excel
```

> [!NOTE]
> La estructura de carpetas de datos de importación (`data/rutasBloqueadas/` y `data/shapes/`) se conserva en Git mediante archivos `.gitkeep` marcados como marcadores de posición, mientras que el contenido real de datos pesados está protegido y se mantiene **100% privado** fuera de GitHub mediante un archivo `.gitignore` optimizado.

---

## 🛠️ Requisitos de Instalación

El módulo cuenta con dependencias externas declaradas en el manifiesto que Odoo comprobará automáticamente:

```python
'external_dependencies': {
    'python': ['shapefile', 'pandas', 'openpyxl'],
}
```

Para instalarlas en tu servidor o contenedor de Odoo, ejecuta:
```bash
pip install pyshp pandas openpyxl
```

---

## 🔧 Configuración y Calibración del Mapa

Odoo cuenta con parámetros globales para realizar **calibraciones manuales micrométricas** en caso de que tus Shapefiles tengan ligeros desfases viales acumulados por datums desactualizados:

1. Activa el **Modo Desarrollador**.
2. Ve a **Ajustes** $\rightarrow$ **Técnico** $\rightarrow$ **Parámetros del Sistema** *(System Parameters)*.
3. Puedes crear/modificar los siguientes parámetros decimales para ajustar el mapa hacia el Norte/Sur o Este/Oeste sin tocar el código fuente:
   * `block_routes.latitude_offset` (Ejemplo: `-0.00045`)
   * `block_routes.longitude_offset` (Ejemplo: `0.00032`)

Cualquier importación manual o programada (vía Cron) aplicará automáticamente estos factores de corrección en el GeoJSON resultante.

---

## ⏱️ Ejecución y Auditoría de los Crons Diarios

Para verificar u optimizar las horas de ejecución de las automatizaciones:

1. Ve a **Ajustes** $\rightarrow$ **Técnico** $\rightarrow$ **Acciones Planificadas** *(Scheduled Actions)*.
2. Busca e inspecciona las tareas:
   * `Block Routes: Importar bloqueos desde Excel`
   * `Block Routes: Sincronizar mapas desde Shapefile`
3. Puedes hacer clic en **Ejecutar Manualmente** para correrlos inmediatamente.

### Registro de Logs Físicos:
Para ver el estado de los datos, filas procesadas, posibles errores en el Excel o problemas de geodatos:
* **Ubicación en Servidor Local (Windows):** `C:\odoo_import_logs\`
  * `excel_importer.log`
  * `shape_importer.log`
* **Ubicación en Contenedores / Servidores Linux:** `~/odoo_import_logs/`
