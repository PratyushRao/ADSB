<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import RadarMap from './components/Map.svelte';
  import Sidebar from './components/Sidebar.svelte';
  import AircraftDetailModal from './components/AircraftDetailModal.svelte';
  import ConnectionModal from './components/ConnectionModal.svelte';
  import type { Aircraft, FeedStatus, ReceiverLocation } from './types/aircraft';
  import { DEFAULT_RECEIVER, createInitialSimulation, advanceSimulation } from './utils/mockData';
  import { parseAdsbPayload } from './utils/parser';

  // Application State
  let receiver = $state<ReceiverLocation>(DEFAULT_RECEIVER);
  let aircraftMap = new Map<string, Aircraft>();
  let aircraftList = $state<Aircraft[]>([]);
  let selectedPlane = $state<Aircraft | null>(null);

  // View Settings
  let showRangeRings = $state(true);
  let showTrails = $state(true);
  let mapLayer = $state<'dark' | 'osm' | 'satellite'>('dark');
  let isSettingsOpen = $state(false);
  let isSidebarOpenMobile = $state(false);

  // Feed / Connection State
  let feedStatus = $state<FeedStatus>({
    mode: 'simulation',
    connected: true,
    endpointUrl: 'ws://127.0.0.1:8000/ws',
    pollingIntervalMs: 1000,
    lastFetchTime: null,
    lastMessageCount: 0,
    totalMessagesReceived: 0,
    error: null,
  });

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let simTimer: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    // Connect to the local backend straight away (demo flights are still
    // available from Settings -> Simulation).
    startFeedConnection(feedStatus.endpointUrl, feedStatus.pollingIntervalMs);
  });

  /** Ask the backend where the antenna is (python main.py --lat .. --lon ..). */
  async function fetchReceiverFromBackend(feedUrl: string) {
    try {
      const u = new URL(feedUrl);
      u.protocol = u.protocol === 'wss:' ? 'https:' : u.protocol === 'ws:' ? 'http:' : u.protocol;
      u.pathname = '/api/receiver';
      u.search = '';
      const res = await fetch(u.toString(), { headers: { Accept: 'application/json' } });
      if (!res.ok) return;
      const rx = await res.json();
      if (rx && typeof rx.lat === 'number' && typeof rx.lon === 'number') {
        handleUpdateReceiver(rx as ReceiverLocation);
      }
    } catch {
      // Backend without /api/receiver (or a third-party feed): keep current location
    }
  }

  onDestroy(() => {
    stopTimers();
  });

  let socket: WebSocket | null = null;

  function stopTimers() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (simTimer) {
      clearInterval(simTimer);
      simTimer = null;
    }
    if (socket) {
      socket.close();
      socket = null;
    }
  }

  function startSimulation() {
    stopTimers();
    aircraftList = createInitialSimulation(receiver);
    aircraftMap.clear();
    aircraftList.forEach((a) => aircraftMap.set(a.hex, a));

    feedStatus.mode = 'simulation';
    feedStatus.connected = true;
    feedStatus.error = null;

    simTimer = setInterval(() => {
      aircraftList = advanceSimulation(aircraftList, receiver, 1);
      aircraftMap.clear();
      aircraftList.forEach((a) => aircraftMap.set(a.hex, a));

      // Keep selected plane updated with latest coordinates
      if (selectedPlane) {
        selectedPlane = aircraftMap.get(selectedPlane.hex) ?? null;
      }
    }, 1000);
  }

  /**
   * Apply a full snapshot from a live backend. The backend's list is
   * authoritative: aircraft missing from it (purged as stale) are dropped,
   * while those still present keep their accumulated trail.
   */
  function applyLiveSnapshot(data: unknown): Aircraft[] {
    const before = Date.now();
    const updated = parseAdsbPayload(data, aircraftMap, receiver).filter(
      (a) => a.lastUpdated >= before
    );
    aircraftList = updated;
    aircraftMap.clear();
    aircraftList.forEach((a) => aircraftMap.set(a.hex, a));
    return updated;
  }

  function startFeedConnection(url: string, intervalMs: number) {
    stopTimers();
    // Drop simulation/previous-feed aircraft so they don't linger
    aircraftMap.clear();
    aircraftList = [];
    feedStatus.endpointUrl = url.trim();
    feedStatus.pollingIntervalMs = intervalMs;
    feedStatus.error = null;
    fetchReceiverFromBackend(feedStatus.endpointUrl);

    // Check if WebSocket stream
    if (feedStatus.endpointUrl.startsWith('ws://') || feedStatus.endpointUrl.startsWith('wss://')) {
      feedStatus.mode = 'websocket';
      feedStatus.connected = false;

      try {
        socket = new WebSocket(feedStatus.endpointUrl);
        socket.onopen = () => {
          feedStatus.connected = true;
          feedStatus.error = null;
        };
        socket.onmessage = (event) => {
          try {
            const updated = applyLiveSnapshot(JSON.parse(event.data));

            feedStatus.lastFetchTime = Date.now();
            feedStatus.lastMessageCount = updated.length;
            feedStatus.totalMessagesReceived += updated.length;

            if (selectedPlane) {
              selectedPlane = aircraftMap.get(selectedPlane.hex) ?? null;
            }
          } catch (e: any) {
            console.error('WebSocket JSON parse error:', e);
          }
        };
        socket.onerror = () => {
          feedStatus.connected = false;
          feedStatus.error = `Can't reach backend at ${feedStatus.endpointUrl} (is python main.py running?)`;
        };
        socket.onclose = () => {
          feedStatus.connected = false;
        };
      } catch (err: any) {
        feedStatus.connected = false;
        feedStatus.error = err?.message || 'Failed to initialize WebSocket';
      }
      return;
    }

    // Default HTTP polling
    feedStatus.mode = 'poll';
    const fetchFeed = async () => {
      try {
        const response = await fetch(feedStatus.endpointUrl, {
          headers: { Accept: 'application/json' },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const updated = applyLiveSnapshot(await response.json());

        feedStatus.connected = true;
        feedStatus.lastFetchTime = Date.now();
        feedStatus.lastMessageCount = updated.length;
        feedStatus.totalMessagesReceived += updated.length;
        feedStatus.error = null;

        if (selectedPlane) {
          selectedPlane = aircraftMap.get(selectedPlane.hex) ?? null;
        }
      } catch (err: any) {
        feedStatus.connected = false;
        feedStatus.error = err?.message || 'Failed to connect to backend endpoint';
      }
    };

    fetchFeed();
    pollTimer = setInterval(fetchFeed, intervalMs);
  }

  function handleUpdateEndpoint(url: string, intervalMs: number) {
    startFeedConnection(url, intervalMs);
  }

  function handleToggleSimulation(enable: boolean) {
    if (enable) {
      startSimulation();
    } else {
      stopTimers();
      feedStatus.mode = 'poll';
      feedStatus.connected = false;
    }
  }

  function handleLoadJsonContent(jsonText: string) {
    try {
      stopTimers();
      const data = JSON.parse(jsonText);
      const updated = parseAdsbPayload(data, aircraftMap, receiver);
      aircraftList = updated;
      aircraftMap.clear();
      aircraftList.forEach((a) => aircraftMap.set(a.hex, a));

      feedStatus.mode = 'file';
      feedStatus.connected = true;
      feedStatus.lastFetchTime = Date.now();
      feedStatus.lastMessageCount = updated.length;
      feedStatus.error = null;

      if (selectedPlane) {
        selectedPlane = aircraftMap.get(selectedPlane.hex) ?? null;
      }
    } catch (err: any) {
      alert(`Invalid JSON: ${err.message}`);
    }
  }

  function handleUpdateReceiver(newReceiver: ReceiverLocation) {
    receiver = newReceiver;
    // Recompute distances for existing planes
    const updated = parseAdsbPayload(aircraftList, new Map<string, Aircraft>(), receiver);
    aircraftList = updated;
    aircraftMap.clear();
    aircraftList.forEach((a) => aircraftMap.set(a.hex, a));
  }

  function handleSelectPlane(plane: Aircraft | null) {
    selectedPlane = plane;
    // On mobile, close sidebar when plane is tapped
    if (plane) {
      isSidebarOpenMobile = false;
    }
  }
</script>

<div class="relative w-screen h-screen overflow-hidden flex bg-slate-950 font-sans">
  <!-- Mobile Sidebar Toggle Button -->
  <button
    onclick={() => (isSidebarOpenMobile = !isSidebarOpenMobile)}
    class="md:hidden absolute top-4 left-4 z-30 p-2.5 rounded-xl bg-slate-900/90 text-cyan-400 border border-slate-700 shadow-xl backdrop-blur-md"
    aria-label="Toggle Navigation"
  >
    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  </button>

  <!-- Left Sidebar (Responsive) -->
  <div
    class="fixed md:static inset-y-0 left-0 z-30 transform transition-transform duration-300 ease-in-out md:translate-x-0 {isSidebarOpenMobile ? 'translate-x-0' : '-translate-x-full'}"
  >
    <Sidebar
      aircraft={aircraftList}
      {selectedPlane}
      {feedStatus}
      {receiver}
      {showRangeRings}
      {showTrails}
      {mapLayer}
      onSelectPlane={handleSelectPlane}
      onOpenSettings={() => (isSettingsOpen = true)}
      onToggleRangeRings={() => (showRangeRings = !showRangeRings)}
      onToggleTrails={() => (showTrails = !showTrails)}
      onChangeMapLayer={(layer) => (mapLayer = layer)}
    />
  </div>

  <!-- Mobile Overlay Backdrop -->
  {#if isSidebarOpenMobile}
    <div
      role="button"
      tabindex="0"
      onclick={() => (isSidebarOpenMobile = false)}
      onkeydown={(e) => e.key === 'Escape' && (isSidebarOpenMobile = false)}
      class="md:hidden fixed inset-0 bg-black/60 z-20 backdrop-blur-xs"
      aria-label="Close Sidebar"
    ></div>
  {/if}

  <!-- Main Map Canvas -->
  <main class="flex-1 relative h-full w-full">
    <RadarMap
      aircraft={aircraftList}
      {selectedPlane}
      {receiver}
      {showRangeRings}
      {showTrails}
      {mapLayer}
      onSelectPlane={handleSelectPlane}
    />

    <!-- Selected Aircraft Inspector Floating HUD -->
    {#if selectedPlane}
      <div class="absolute bottom-5 left-4 md:left-6 z-20 max-w-lg w-[calc(100%-2rem)] md:w-auto animate-slide-up">
        <AircraftDetailModal
          plane={selectedPlane}
          onClose={() => (selectedPlane = null)}
        />
      </div>
    {/if}

    <!-- Backend Connection Warning Banner -->
    {#if feedStatus.error && (feedStatus.mode === 'poll' || feedStatus.mode === 'websocket')}
      <div class="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-4 py-2 rounded-xl bg-rose-950/90 border border-rose-700/80 text-rose-200 text-xs font-mono shadow-2xl backdrop-blur-md flex items-center gap-2">
        <span>⚠️</span>
        <span>{feedStatus.error}</span>
        <button
          onclick={() => (isSettingsOpen = true)}
          class="underline hover:text-white font-bold ml-2"
        >
          Check Settings
        </button>
      </div>
    {/if}
  </main>

  <!-- Data Source Configuration Modal -->
  <ConnectionModal
    isOpen={isSettingsOpen}
    {feedStatus}
    {receiver}
    onClose={() => (isSettingsOpen = false)}
    onUpdateEndpoint={handleUpdateEndpoint}
    onLoadJsonContent={handleLoadJsonContent}
    onUpdateReceiver={handleUpdateReceiver}
    onToggleSimulation={handleToggleSimulation}
  />
</div>
