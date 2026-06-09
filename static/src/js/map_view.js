/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS, loadCSS } from "@web/core/assets";
import { session } from "@web/session";

export class MapViewer extends Component {
    setup() {
        this.orm = useService("orm");
        
        this.state = useState({
            loading: true,
            locationStatus: "Obteniendo...",
            currentRoute: null,
            currentRouteBlocked: false,
            blockReason: "",
            lat: -1.8312, // Ecuador center
            lng: -78.1834
        });
        
        this.map = null;
        this.routeLayers = [];
        this.userMarker = null;

        onWillStart(async () => {
            // Cargar Leaflet dinámicamente para evitar errores del compilador de Odoo
            await Promise.all([
                loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
                loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js")
            ]);
        });

        onMounted(() => {
            this.initMap();
            this.loadRoutesAndBlocked();
            this.startLocationTracking();
        });
    }

    initMap() {
        if (!window.L) {
            console.error("Leaflet not loaded");
            return;
        }
        
        // Centrar por defecto en Ecuador (lat: -1.8312, lng: -78.1834, zoom: 7)
        this.map = L.map('block_routes_map').setView([this.state.lat, this.state.lng], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);
    }

    async loadRoutesAndBlocked() {
        try {
            // 1. Cargar bloqueos activos
            const blockedRoutes = await this.orm.searchRead('block_routes.blocked', [], ['route_id', 'reason', 'date_start', 'date_end']);
            const now = new Date();
            this.blockedRoutesMap = {};
            blockedRoutes.forEach(br => {
                if (br.date_start && br.date_end) {
                    const start = new Date(br.date_start.replace(' ', 'T') + 'Z');
                    const end = new Date(br.date_end.replace(' ', 'T') + 'Z');
                    if (now >= start && now <= end) {
                        this.blockedRoutesMap[br.route_id[0]] = {
                            reason: br.reason || 'Bloqueado',
                            date_start: br.date_start,
                            date_end: br.date_end
                        };
                    }
                }
            });
            
            // 2. Obtener compañía y unidad de negocio
            const companyId = session.user_companies?.current_company || session.company_id;
            const company = await this.orm.read('res.company', [companyId], ['business_unit']);
            const businessUnit = company[0] ? company[0].business_unit : false;
            
            // 3. Cargar rutas
            const domain = businessUnit ? ['|', ['business_unit', '=', false], ['business_unit', '=', businessUnit]] : [];
            this.routes = await this.orm.searchRead('block_routes.route', domain, ['name', 'geojson']);

            // 4. Dibujar en el mapa
            this.loadRoutesOnMap();
        } catch (e) {
            console.error("Error al cargar rutas o bloqueos:", e);
            this.state.loading = false;
        }
    }

    loadRoutesOnMap() {
        this.state.loading = false;
        this.routeLayers = [];
        
        this.routes.forEach(route => {
            try {
                const geojsonData = JSON.parse(route.geojson);
                const isBlocked = this.blockedRoutesMap[route.id] !== undefined;
                
                const style = {
                    color: isBlocked ? '#dc3545' : '#28a745',
                    weight: 3.5,
                    opacity: 0.8,
                    fillColor: isBlocked ? '#dc3545' : '#28a745',
                    fillOpacity: 0.25
                };
                
                let popupContent = `<b>${route.name}</b><br/>`;
                if (isBlocked) {
                    const blockInfo = this.blockedRoutesMap[route.id];
                    popupContent += `<b>BLOQUEADA:</b> ${blockInfo.reason}<br/>`;
                    popupContent += `<b>Desde:</b> ${blockInfo.date_start}<br/>`;
                    popupContent += `<b>Hasta:</b> ${blockInfo.date_end}`;
                } else {
                    popupContent += 'Libre';
                }
                
                const layer = L.geoJSON(geojsonData, {
                    style: style
                }).bindPopup(popupContent);
                
                // Keep reference for PIP (Point In Polygon) checking
                layer.routeId = route.id;
                layer.routeName = route.name;
                layer.isBlocked = isBlocked;
                layer.blockReason = isBlocked ? this.blockedRoutesMap[route.id].reason : '';
                
                layer.addTo(this.map);
                this.routeLayers.push(layer);
            } catch (e) {
                console.error("Error parsing geojson for route", route.name, e);
            }
        });

        // Enfocar automáticamente el mapa en la extensión de todas las rutas cargadas
        if (this.routeLayers.length > 0) {
            const group = new L.featureGroup(this.routeLayers);
            this.map.fitBounds(group.getBounds(), { padding: [30, 30] });
        }
    }

    startLocationTracking() {
        if ("geolocation" in navigator) {
            navigator.geolocation.watchPosition(
                (position) => {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    
                    this.state.locationStatus = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
                    this.updateUserMarker(lat, lng);
                    this.checkCurrentRoute(lat, lng);
                },
                (error) => {
                    console.error("Geolocation error:", error);
                    this.state.locationStatus = "Error / Denegado";
                },
                { enableHighAccuracy: true }
            );
        } else {
            this.state.locationStatus = "No soportado";
        }
    }

    updateUserMarker(lat, lng) {
        if (this.userMarker) {
            this.userMarker.setLatLng([lat, lng]);
        } else {
            // Un marcador distintivo para el usuario
            this.userMarker = L.circleMarker([lat, lng], {
                color: '#000',
                fillColor: '#00ff00',
                fillOpacity: 1,
                radius: 8
            }).addTo(this.map).bindPopup("Tu ubicación actual");
            
            // Centrar mapa a la ubicación del usuario solo la primera vez
            this.map.setView([lat, lng], 14);
        }
    }

    checkCurrentRoute(lat, lng) {
        // Simple bounding box or ray casting check
        // For accurate PIP, a library like Turf.js is better, but we can do a basic check
        // Using Leaflet PIP or simple bounds check for now
        
        let foundRoute = null;
        let pt = L.latLng(lat, lng);
        
        // This is a naive check. For true polygon checking, turf.booleanPointInPolygon is recommended.
        // As a fallback, we check if the point is within the bounds of the layer
        for (const layer of this.routeLayers) {
            let bounds = layer.getBounds();
            if (bounds.contains(pt)) {
                // Warning: This only checks bounding box. 
                // In a production app with complex shapes, we should use Leaflet-PIP or Turf.js
                foundRoute = layer;
                break;
            }
        }
        
        if (foundRoute) {
            this.state.currentRoute = foundRoute.routeName;
            this.state.currentRouteBlocked = foundRoute.isBlocked;
            this.state.blockReason = foundRoute.blockReason;
        } else {
            this.state.currentRoute = null;
        }
    }
}

MapViewer.template = "block_routes.map_view";

registry.category("actions").add("block_routes.map_view", MapViewer);
