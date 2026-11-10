<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import L from 'leaflet';
  import type { Aircraft, ReceiverLocation } from '../types/aircraft';
  import { formatAltitude, formatCoords } from '../utils/geo';

  interface Props {
    aircraft: Aircraft[];
    selectedPlane: Aircraft | null;
    receiver: ReceiverLocation;
    mapLayer?: 'osm' | 'satellite' | 'dark';
    onSelectPlane: (plane: Aircraft | null) => void;
  }

  let {
    aircraft = [],
    selectedPlane = null,
    receiver,
    mapLayer = 'osm',
    onSelectPlane,
  }: Props = $props();

  let mapContainer: HTMLDivElement | null = null;
  let map: L.Map | null = null;
  let currentTileLayer: L.TileLayer | null = null;
  let currentLayerType: 'osm' | 'satellite' | 'dark' | null = null;
  let resizeObserver: ResizeObserver | null = null;

  // Markers storage
  const markers = new Map<string, L.Marker>();
  let receiverMarker: L.Marker | null = null;

  const TILE_PROVIDERS = {
    osm: {
      url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxNativeZoom: 19,
      maxZoom: 19,
    },
    satellite: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and GIS User Community',
      maxNativeZoom: 18,
      maxZoom: 19,
    },
    dark: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; Dark Canvas',
      maxNativeZoom: 16,
      maxZoom: 19,
    },
  };

  onMount(() => {
    if (!mapContainer) return;

    // Initialize Leaflet map with standard Street layer default
    map = L.map(mapContainer, {
      center: [receiver.lat, receiver.lon],
      zoom: 9,
      zoomControl: false,
    });

    updateTileLayer(mapLayer);
    updateReceiver();
    updateAircraftMarkers();

    // Invalidate map size once DOM has fully settled to prevent blank boundary tiles
    requestAnimationFrame(() => {
      map?.invalidateSize();
    });

    // Automatically recalculate map size on window/layout resize
    resizeObserver = new ResizeObserver(() => {
      map?.invalidateSize();
    });
    resizeObserver.observe(mapContainer);

    // Clicking map background deselects plane
    map.on('click', (e) => {
      const target = (e.originalEvent?.target as HTMLElement) || null;
      if (target && !target.closest('.plane-marker')) {
        onSelectPlane(null);
      }
    });
  });

  onDestroy(() => {
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
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

  // Watch aircraft updates
  $effect(() => {
    if (aircraft && map) {
      updateAircraftMarkers();
    }
  });

  // Pan to selected plane smoothly
  $effect(() => {
    if (selectedPlane && map) {
      const marker = markers.get(selectedPlane.hex);
      if (marker) {
        map.panTo([selectedPlane.lat, selectedPlane.lon], { animate: true, duration: 0.5 });
      }
    }
  });

  function updateTileLayer(layerType: 'osm' | 'satellite' | 'dark') {
    if (!map) return;
    // Prevent duplicate layer re-creation if already active
    if (currentLayerType === layerType && currentTileLayer && map.hasLayer(currentTileLayer)) {
      return;
    }

    if (currentTileLayer) {
      map.removeLayer(currentTileLayer);
      currentTileLayer = null;
    }

    const config = TILE_PROVIDERS[layerType] || TILE_PROVIDERS.osm;
    currentLayerType = layerType;
    currentTileLayer = L.tileLayer(config.url, {
      attribution: config.attribution,
      maxZoom: config.maxZoom || 19,
      maxNativeZoom: config.maxNativeZoom || 19,
      crossOrigin: true,
      keepBuffer: 3,
      updateWhenIdle: false,
      updateWhenZooming: false,
    });

    currentTileLayer.on('tileerror', (e) => {
      console.warn('Map tile failed to load:', e.coords);
    });

    currentTileLayer.addTo(map);
  }

  function updateReceiver() {
    if (!map) return;

    // Receiver Pulse Marker
    const rxIcon = L.divIcon({
      className: 'receiver-icon-wrapper',
      html: `
        <div class="relative flex items-center justify-center w-8 h-8 pointer-events-auto cursor-pointer group">
          <div class="absolute w-8 h-8 rounded-full bg-[#168AAD]/20 animate-radar-pulse"></div>
          <div class="absolute w-5 h-5 rounded-full bg-[#168AAD]/30"></div>
          <div class="relative w-3.5 h-3.5 rounded-full bg-[#168AAD] border-2 border-white shadow-md flex items-center justify-center">
            <div class="w-1 h-1 rounded-full bg-white"></div>
          </div>
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

      receiverMarker.bindTooltip(
        `<div class="font-sans text-xs">
          <div class="font-medium text-[#263747] flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-[#239B75]"></span>
            ${receiver.name}
          </div>
          <div class="font-mono text-xs text-[#718096] mt-0.5 tabular-nums">${formatCoords(receiver.lat, receiver.lon)}</div>
          <div class="text-xs text-[#168AAD] font-normal mt-1">Ground Station Antenna</div>
        </div>`,
        {
          direction: 'top',
          className: 'bg-white text-[#263747] border border-[#E3EAF0] rounded-xl p-2 shadow-lg backdrop-blur-sm',
          offset: [0, -10],
        }
      );
    }
  }

  function getAltitudeColor(altitudeFeet: number): string {
    if (altitudeFeet <= 0) return '#64748B'; // slate (ground)
    if (altitudeFeet < 10000) return '#0284C7'; // sky blue (low)
    if (altitudeFeet < 25000) return '#168AAD'; // teal (mid)
    if (altitudeFeet < 35000) return '#2563EB'; // cobalt (cruise)
    return '#7C3AED'; // violet (high FL)
  }

  function createPlaneIcon(plane: Aircraft, isSelected: boolean) {
    const altColor = getAltitudeColor(plane.altitude);
    const heading = Math.round(plane.heading);
    const isClimbing = (plane.verticalRate ?? 0) > 200;
    const isDescending = (plane.verticalRate ?? 0) < -200;
    const vIndicator = isClimbing ? '↑' : isDescending ? '↓' : '';

    const iconColor = isSelected ? '#168AAD' : altColor;

    return L.divIcon({
      className: 'plane-marker',
      html: `
        <div class="relative flex items-center justify-center w-9 h-9 group">
          <!-- Selection Pulsing Ring Halo -->
          ${
            isSelected
              ? `<div class="absolute inset-0 rounded-full border-2 border-[#168AAD] bg-[#168AAD]/15 animate-pulse pointer-events-none"></div>`
              : ''
          }
          
          <!-- Aerodynamic Jet SVG Silhouette with Center Rotation -->
          <div 
            class="plane-marker-icon-wrapper flex items-center justify-center filter drop-shadow-[0_2px_4px_rgba(38,55,71,0.25)] select-none"
            style="transform: rotate(${heading}deg); width: 28px; height: 28px;"
          >
            <svg viewBox="0 0 24 24" class="w-full h-full" style="color: ${iconColor};">
              <!-- Crisp white outer stroke outline for contrast over map tiles -->
              <path
                d="M12 2C11.4 2 11 2.5 11 3.2V8.5L3.5 13V15L11 12.8V18.2L8.5 20.2V22L12 21L15.5 22V20.2L13 18.2V12.8L20.5 15V13L13 8.5V3.2C13 2.5 12.6 2 12 2Z"
                fill="currentColor"
                stroke="#FFFFFF"
                stroke-width="1.2"
                stroke-linejoin="round"
              />
            </svg>
          </div>

          <!-- Callsign & Altitude Compact Pill Badge -->
          <div class="absolute top-full left-1/2 -translate-x-1/2 mt-0.5 flex items-center gap-1.5 px-2 py-0.5 rounded-md shadow-xs border whitespace-nowrap ${isSelected ? 'border-[#168AAD] bg-[#F0F8FA]' : 'border-[#E3EAF0] bg-white/95'} backdrop-blur-md pointer-events-none select-none transition-all">
            <span class="text-xs font-sans font-semibold ${isSelected ? 'text-[#168AAD]' : 'text-[#263747]'}">
              ${plane.callsign}
            </span>
            <span class="text-xs font-mono font-medium tabular-nums" style="color: ${altColor}">
              ${formatAltitude(plane.altitude)} ${vIndicator}
            </span>
            ${
              isSelected && plane.route
                ? `<span class="text-xs font-sans font-medium text-[#168AAD] border-l border-[#E3EAF0] pl-1.5">${plane.route.origin.iata || plane.route.origin.icao || '?'}→${plane.route.destination.iata || plane.route.destination.icao || '?'}</span>`
                : ''
            }
          </div>
        </div>
      `,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
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
    }

    // Prune removed planes
    for (const [hex, marker] of markers.entries()) {
      if (!currentHexSet.has(hex)) {
        map.removeLayer(marker);
        markers.delete(hex);
      }
    }
  }

  export function zoomIn() {
    map?.zoomIn();
  }

  export function zoomOut() {
    map?.zoomOut();
  }

  export function centerOnReceiver() {
    if (map && receiver) {
      map.flyTo([receiver.lat, receiver.lon], 9, { duration: 0.8 });
    }
  }

  export function fitAllAircraft() {
    if (!map || aircraft.length === 0) return;
    const group = L.featureGroup(Array.from(markers.values()));
    map.fitBounds(group.getBounds().pad(0.15), { animate: true, duration: 0.8 });
  }
</script>

<div class="relative w-full h-full select-none">
  <div bind:this={mapContainer} class="w-full h-full z-0"></div>

  <!-- Floating Map Controls Dock (Frosted Glassmorphism, Top-Right) -->
  <div class="absolute top-4 right-4 z-20 flex flex-col gap-2">
    <!-- Navigation & Zoom Control Cluster -->
    <div class="glass-panel p-1 rounded-xl flex flex-col gap-1 shadow-md bg-white/90 backdrop-blur-md border border-[#E3EAF0]">
      <button
        onclick={zoomIn}
        class="w-8 h-8 rounded-lg flex items-center justify-center text-[#263747] hover:text-[#168AAD] hover:bg-[#F4F7FA] transition active:scale-95"
        title="Zoom In"
        aria-label="Zoom In"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M12 4v16m8-8H4" />
        </svg>
      </button>

      <button
        onclick={zoomOut}
        class="w-8 h-8 rounded-lg flex items-center justify-center text-[#263747] hover:text-[#168AAD] hover:bg-[#F4F7FA] transition active:scale-95"
        title="Zoom Out"
        aria-label="Zoom Out"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M20 12H4" />
        </svg>
      </button>

      <div class="w-full h-[1px] bg-[#E3EAF0] my-0.5"></div>

      <button
        onclick={centerOnReceiver}
        class="w-8 h-8 rounded-lg flex items-center justify-center text-[#263747] hover:text-[#168AAD] hover:bg-[#F4F7FA] transition active:scale-95"
        title="Center Antenna Location"
        aria-label="Center Antenna Location"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="9" stroke-width="2" />
          <circle cx="12" cy="12" r="3" fill="currentColor" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v3m0 12v3M3 12h3m12 0h3" />
        </svg>
      </button>

      <button
        onclick={fitAllAircraft}
        class="w-8 h-8 rounded-lg flex items-center justify-center text-[#263747] hover:text-[#168AAD] hover:bg-[#F4F7FA] transition active:scale-95"
        title="Fit All Aircraft in View"
        aria-label="Fit All Aircraft"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
        </svg>
      </button>
    </div>
  </div>
</div>
