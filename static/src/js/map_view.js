/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MapViewer extends Component {
    setup() {
        this.orm = useService("orm");
        this.user = useService("user");
        
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
            // Load blocked routes to memory
            const blockedRoutes = await this.orm.searchRead('block_routes.blocked', [], ['route_id', 'reason']);
            this.blockedRoutesMap = {};
            blockedRoutes.forEach(br => {
                this.blockedRoutesMap[br.route_id[0]] = br.reason || 'Bloqueado';
            });
            
            // Get user's company's business_unit
            const company = await this.orm.read('res.company', [this.user.companyId], ['business_unit']);
            const businessUnit = company[0] ? company[0].business_unit : false;
            
            // Load routes
            const domain = businessUnit ? ['|', ['business_unit', '=', false], ['business_unit', '=', businessUnit]] : [];
            this.routes = await this.orm.searchRead('block_routes.route', domain, ['name', 'geojson']);
        });

        onMounted(() => {
            this.initMap();
            this.loadRoutesOnMap();
            this.startLocationTracking();
        });
    }

    initMap() {
        if (!window.L) {
            console.error("Leaflet not loaded");
            return;
        }
        
        this.map = L.map('block_routes_map').setView([this.state.lat, this.state.lng], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);
    }

    loadRoutesOnMap() {
        this.state.loading = false;
        
        this.routes.forEach(route => {
            try {
                const geojsonData = JSON.parse(route.geojson);
                const isBlocked = this.blockedRoutesMap[route.id] !== undefined;
                
                const style = {
                    color: isBlocked ? '#ff0000' : '#3388ff',
                    weight: 3,
                    opacity: 0.7,
                    fillOpacity: 0.2
                };
                
                const layer = L.geoJSON(geojsonData, {
                    style: style
                }).bindPopup(`<b>${route.name}</b><br/>${isBlocked ? 'BLOQUEADA: ' + this.blockedRoutesMap[route.id] : 'Libre'}`);
                
                // Keep reference for PIP (Point In Polygon) checking
                layer.routeId = route.id;
                layer.routeName = route.name;
                layer.isBlocked = isBlocked;
                layer.blockReason = isBlocked ? this.blockedRoutesMap[route.id] : '';
                
                layer.addTo(this.map);
                this.routeLayers.push(layer);
            } catch (e) {
                console.error("Error parsing geojson for route", route.name, e);
            }
        });
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
