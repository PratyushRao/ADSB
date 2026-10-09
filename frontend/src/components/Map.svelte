<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import L from 'leaflet';
  import type { Aircraft, ReceiverLocation } from '../types/aircraft';
  import { formatAltitude, formatSpeed, formatCoords } from '../utils/geo';

  interface Props {
    aircraft: Aircraft[];
    selectedPlane: Aircraft | null;
    receiver: ReceiverLocation;
    showRangeRings?: boolean;
    showTrails?: boolean;
    mapLayer?: 'dark' | 'osm' | 'satellite';
    onSelectPlane: (plane: Aircraft | null) => void;
  }

  let {
    aircraft = [],
    selectedPlane = null,
    receiver,
    showRangeRings = true,
    showTrails = true,
    mapLayer = 'dark',
    onSelectPlane,
  }: Props = $props();

  let mapContainer: HTMLDivElement | null = null;
  let map: L.Map | null = null;
  let currentTileLayer: L.TileLayer | null = null;

  // Markers and overlays storage
  const markers = new Map<string, L.Marker>();
  const trails = new Map<string, L.Polyline>();
  let receiverMarker: L.Marker | null = null;
  let rangeCircles: L.Circle[] = [];

  const TILE_PROVIDERS = {
    dark: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; Dark Canvas',
      maxNativeZoom: 16,
      maxZoom: 19,
    },
    osm: {
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
    satellite: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    },
  };

  onMount(() => {
    if (!mapContainer) return;

    // Initialize Leaflet map
    map = L.map(mapContainer, {
      center: [receiver.lat, receiver.lon],
      zoom: 9,
      zoomControl: false,
    });

    // Custom top-right zoom control
    L.control.zoom({ position: 'topright' }).addTo(map);

    updateTileLayer(mapLayer);
    updateReceiver();
    updateAircraftMarkers();

    // Map click outside deselects
    map.on('click', (e) => {
      // If clicking directly on map canvas, clear selection
      const target = (e.originalEvent?.target as HTMLElement) || null;
      if (target && !target.closest('.plane-marker')) {
        onSelectPlane(null);
      }
    });
  });

  onDestroy(() => {
    if (map) {
      map.remove();
      map = null;
    }
  });

  // Watch layer change
  $effect(() => {
    updateTileLayer(mapLayer);
  });

  // Watch receiver change
  $effect(() => {
    if (receiver && map) {
      updateReceiver();
    }
  });

  // Watch range rings toggle
  $effect(() => {
    toggleRangeRings(showRangeRings);
  });

  // Watch aircraft updates
  $effect(() => {
    if (aircraft && map) {
      updateAircraftMarkers();
    }
  });

  // Center on selected plane if selected
  $effect(() => {
    if (selectedPlane && map) {
      const marker = markers.get(selectedPlane.hex);
      if (marker) {
        map.panTo([selectedPlane.lat, selectedPlane.lon], { animate: true, duration: 0.5 });
      }
    }
  });

  function updateTileLayer(layerType: 'dark' | 'osm' | 'satellite') {
    if (!map) return;
    if (currentTileLayer) {
      map.removeLayer(currentTileLayer);
    }
    const config = TILE_PROVIDERS[layerType] || TILE_PROVIDERS.dark;
    currentTileLayer = L.tileLayer(config.url, {
      attribution: config.attribution,
      maxZoom: 19,
      maxNativeZoom: (config as any).maxNativeZoom || 19,
      subdomains: 'abcd',
    }).addTo(map);
  }

  function updateReceiver() {
    if (!map) return;

    // Clear old range circles
    rangeCircles.forEach((c) => map?.removeLayer(c));
    rangeCircles = [];

    // Receiver Pulse DivIcon
    const rxIcon = L.divIcon({
      className: 'receiver-icon-wrapper',
      html: `
        <div class="relative flex items-center justify-center w-8 h-8">
          <div class="absolute w-8 h-8 rounded-full bg-cyan-500/20 animate-ping"></div>
          <div class="absolute w-4 h-4 rounded-full bg-cyan-500/40"></div>
          <div class="w-2.5 h-2.5 rounded-full bg-cyan-400 border-2 border-white shadow-lg"></div>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });

    if (receiverMarker) {
      receiverMarker.setLatLng([receiver.lat, receiver.lon]);
    } else {
      receiverMarker = L.marker([receiver.lat, receiver.lon], {
        icon: rxIcon,
        zIndexOffset: 100,
      }).addTo(map);

      receiverMarker.bindTooltip(`📡 ${receiver.name}<br>${formatCoords(receiver.lat, receiver.lon)}`, {
        direction: 'top',
        className: 'bg-slate-900 text-cyan-300 font-mono text-xs border border-cyan-800 rounded p-1.5 shadow-xl',
      });
    }

    // Add Range Rings (10 NM, 25 NM, 50 NM, 100 NM)
    const NM_TO_METERS = 1852;
    const ringDistancesNm = [10, 25, 50, 100];
    ringDistancesNm.forEach((nm) => {
      const circle = L.circle([receiver.lat, receiver.lon], {
        radius: nm * NM_TO_METERS,
        color: '#06b6d4',
        weight: 1,
        dashArray: '4, 8',
        fill: false,
        opacity: 0.35,
        interactive: false,
      });

      if (showRangeRings) {
        circle.addTo(map!);
      }
      rangeCircles.push(circle);
    });
  }

  function toggleRangeRings(show: boolean) {
    if (!map) return;
    rangeCircles.forEach((c) => {
      if (show) {
        if (!map?.hasLayer(c)) c.addTo(map!);
      } else {
        if (map?.hasLayer(c)) map.removeLayer(c);
      }
    });
  }

  function getAltitudeColor(altitudeFeet: number): string {
    if (altitudeFeet < 5000) return '#38bdf8'; // light sky blue (low)
    if (altitudeFeet < 15000) return '#4ade80'; // green (mid-low)
    if (altitudeFeet < 25000) return '#facc15'; // yellow (mid)
    if (altitudeFeet < 35000) return '#fb923c'; // orange (cruise)
    return '#f43f5e'; // rose/magenta (high FL)
  }

  function createPlaneIcon(plane: Aircraft, isSelected: boolean) {
    const altColor = getAltitudeColor(plane.altitude);
    const heading = Math.round(plane.heading);
    const isClimbing = (plane.verticalRate ?? 0) > 200;
    const isDescending = (plane.verticalRate ?? 0) < -200;
    const vIndicator = isClimbing ? '▲' : isDescending ? '▼' : '';

    return L.divIcon({
      className: 'plane-marker',
      html: `
        <div class="relative flex flex-col items-center justify-center -translate-x-1/2 -translate-y-1/2 group">
          <!-- Selection Glow Ring -->
          ${
            isSelected
              ? `<div class="absolute -inset-2.5 rounded-full border-2 border-cyan-400 bg-cyan-400/20 animate-pulse pointer-events-none"></div>`
              : ''
          }
          
          <!-- Airplane Emoji Container with Rotation -->
          <div 
            class="transform transition-transform duration-300 ease-out select-none drop-shadow-[0_4px_8px_rgba(0,0,0,0.9)]"
            style="transform: rotate(${heading}deg); font-size: 26px; line-height: 1;"
          >
            ✈️
          </div>

          <!-- Callsign & Altitude Badge -->
          <div class="mt-0.5 flex items-center gap-1 px-1.5 py-0.5 rounded shadow-lg border border-slate-700/80 bg-slate-950/90 backdrop-blur-sm pointer-events-none select-none">
            <span class="text-[10px] font-bold font-mono tracking-wider ${isSelected ? 'text-cyan-300 font-extrabold' : 'text-slate-100'}">
              ${plane.callsign}
            </span>
            <span class="text-[9px] font-mono font-medium" style="color: ${altColor}">
              ${formatAltitude(plane.altitude)} ${vIndicator}
            </span>
          </div>
        </div>
      `,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
    });
  }

  function updateAircraftMarkers() {
    if (!map) return;

    const currentHexSet = new Set<string>();

    for (const plane of aircraft) {
      currentHexSet.add(plane.hex);
      const isSelected = selectedPlane?.hex === plane.hex;
      const icon = createPlaneIcon(plane, isSelected);

      let marker = markers.get(plane.hex);
      if (marker) {
        marker.setLatLng([plane.lat, plane.lon]);
        marker.setIcon(icon);
        marker.setZIndexOffset(isSelected ? 1000 : 200);
      } else {
        marker = L.marker([plane.lat, plane.lon], {
          icon,
          zIndexOffset: isSelected ? 1000 : 200,
        }).addTo(map);

        marker.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          onSelectPlane(plane);
        });

        markers.set(plane.hex, marker);
      }

      // Update Polyline flight trails
      if (showTrails && plane.trail && plane.trail.length > 1) {
        let polyline = trails.get(plane.hex);
        const trailColor = isSelected ? '#22d3ee' : getAltitudeColor(plane.altitude);
        const trailOpacity = isSelected ? 0.9 : 0.45;
        const trailWeight = isSelected ? 3 : 2;

        if (polyline) {
          polyline.setLatLngs(plane.trail);
          polyline.setStyle({ color: trailColor, opacity: trailOpacity, weight: trailWeight });
        } else {
          polyline = L.polyline(plane.trail, {
            color: trailColor,
            weight: trailWeight,
            opacity: trailOpacity,
            dashArray: isSelected ? undefined : '3, 4',
            smoothFactor: 1,
            interactive: false,
          }).addTo(map);
          trails.set(plane.hex, polyline);
        }
      } else {
        const polyline = trails.get(plane.hex);
        if (polyline) {
          map.removeLayer(polyline);
          trails.delete(plane.hex);
        }
      }
    }

    // Prune removed planes
    for (const [hex, marker] of markers.entries()) {
      if (!currentHexSet.has(hex)) {
        map.removeLayer(marker);
        markers.delete(hex);
      }
    }

    for (const [hex, polyline] of trails.entries()) {
      if (!currentHexSet.has(hex) || !showTrails) {
        map.removeLayer(polyline);
        trails.delete(hex);
      }
    }
  }

  export function centerOnReceiver() {
    if (map && receiver) {
      map.flyTo([receiver.lat, receiver.lon], 9, { duration: 1 });
    }
  }

  export function fitAllAircraft() {
    if (!map || aircraft.length === 0) return;
    const group = L.featureGroup(Array.from(markers.values()));
    map.fitBounds(group.getBounds().pad(0.15));
  }
</script>

<div class="relative w-full h-full">
  <div bind:this={mapContainer} class="w-full h-full z-0"></div>

  <!-- Map Quick Action Bar (Bottom Right Overlay) -->
  <div class="absolute bottom-5 right-5 z-20 flex flex-col gap-2">
    <button
      onclick={centerOnReceiver}
      class="p-2.5 rounded-xl bg-slate-900/90 text-cyan-400 hover:text-cyan-200 border border-slate-700/80 shadow-2xl backdrop-blur-md transition-all active:scale-95 hover:border-cyan-500/50"
      title="Center on Receiver Antenna"
      aria-label="Center on Receiver"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" stroke-width="2" />
        <circle cx="12" cy="12" r="3" fill="currentColor" />
        <line x1="12" y1="2" x2="12" y2="5" stroke-width="2" />
        <line x1="12" y1="19" x2="12" y2="22" stroke-width="2" />
        <line x1="2" y1="12" x2="5" y2="12" stroke-width="2" />
        <line x1="19" y1="12" x2="22" y2="12" stroke-width="2" />
      </svg>
    </button>

    <button
      onclick={fitAllAircraft}
      class="p-2.5 rounded-xl bg-slate-900/90 text-cyan-400 hover:text-cyan-200 border border-slate-700/80 shadow-2xl backdrop-blur-md transition-all active:scale-95 hover:border-cyan-500/50"
      title="Fit All Aircraft in View"
      aria-label="Fit All Aircraft"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
      </svg>
    </button>
  </div>
</div>
