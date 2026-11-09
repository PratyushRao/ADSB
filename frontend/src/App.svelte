<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import RadarMap from './components/Map.svelte';
  import Sidebar from './components/Sidebar.svelte';
  import AircraftDetailModal from './components/AircraftDetailModal.svelte';
  import ConnectionModal from './components/ConnectionModal.svelte';
  import type { Aircraft, FeedStatus, ReceiverLocation } from './types/aircraft';
  import { DEFAULT_RECEIVER, createInitialSimulation, advanceSimulation } from './utils/mockData';
  import { parseAdsbPayload } from './utils/parser';
  import { formatCoords } from './utils/geo';

  // Application State
  let receiver = $state<ReceiverLocation>(DEFAULT_RECEIVER);
  let aircraftMap = new Map<string, Aircraft>();
  let aircraftList = $state<Aircraft[]>([]);
  let selectedPlane = $state<Aircraft | null>(null);

  // View Settings
  let mapLayer = $state<'osm' | 'satellite' | 'dark'>('osm');
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
  let socket: WebSocket | null = null;
  let nowTime = $state(Date.now());
  let clockTimer: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    // Keep a ticking clock for relative timestamps (e.g. "2s ago")
    clockTimer = setInterval(() => {
      nowTime = Date.now();
    }, 1000);

    // Connect to the local backend straight away (demo flights are still
    // available from Settings -> Simulation).
    startFeedConnection(feedStatus.endpointUrl, feedStatus.pollingIntervalMs);
  });

  onDestroy(() => {
    stopTimers();
    if (clockTimer) {
      clearInterval(clockTimer);
      clockTimer = null;
    }
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
    feedStatus.lastFetchTime = Date.now();
    feedStatus.error = null;

    simTimer = setInterval(() => {
      aircraftList = advanceSimulation(aircraftList, receiver, 1);
      aircraftMap.clear();
      aircraftList.forEach((a) => aircraftMap.set(a.hex, a));
      feedStatus.lastFetchTime = Date.now();
      feedStatus.totalMessagesReceived += aircraftList.length;

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
    // On mobile, close sidebar when plane is selected
    if (plane) {
      isSidebarOpenMobile = false;
    }
  }

  const secondsAgo = $derived(
    feedStatus.lastFetchTime ? Math.max(0, Math.floor((nowTime - feedStatus.lastFetchTime) / 1000)) : null
  );

  const nearestDistanceNm = $derived(
    aircraftList.length > 0
      ? Math.min(...aircraftList.map((a) => a.distanceNm ?? 99999))
      : null
  );
</script>

<div class="h-screen w-screen flex flex-col bg-[#F4F7FA] font-sans overflow-hidden text-[#263747] select-none">
  <!-- Top Navigation Bar -->
  <header class="h-16 bg-white border-b border-[#E3EAF0] px-5 flex items-center justify-between shrink-0 z-30 shadow-2xs">
    <!-- Brand / Logo & Live Pulse Indicator -->
    <div class="flex items-center gap-3.5">
      <!-- Mobile Sidebar Toggle Button -->
      <button
        onclick={() => (isSidebarOpenMobile = !isSidebarOpenMobile)}
        class="md:hidden p-2 rounded-lg bg-[#F4F7FA] hover:bg-[#EAF0F4] border border-[#E3EAF0] text-[#168AAD] transition"
        aria-label="Toggle Aircraft List"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      <div class="w-9 h-9 rounded-xl bg-[#168AAD] text-white flex items-center justify-center shadow-xs">
        <svg class="w-4.5 h-4.5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C11.4 2 11 2.5 11 3.2V8.5L3.5 13V15L11 12.8V18.2L8.5 20.2V22L12 21L15.5 22V20.2L13 18.2V12.8L20.5 15V13L13 8.5V3.2C13 2.5 12.6 2 12 2Z" />
        </svg>
      </div>

      <div class="flex flex-col justify-center">
        <div class="flex items-center gap-2">
          <h1 class="font-bold text-[15px] sm:text-base tracking-wide text-[#263747] font-mono leading-none">
            ADSB RADAR
          </h1>
          <span class="hidden sm:inline-block text-[10px] font-mono px-2 py-0.5 rounded bg-[#EAF5F8] text-[#168AAD] font-semibold border border-[#C5E4EF] leading-none">
            1090 MHz
          </span>
        </div>
        <p class="hidden sm:block text-[10px] text-[#718096] font-sans tracking-normal mt-1 leading-none">
          Live Air Traffic Monitor
        </p>
      </div>

      <!-- Live Stream Status Pill -->
      <div class="ml-2 flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-mono
        {feedStatus.connected || feedStatus.mode === 'simulation'
          ? 'bg-[#EBFBF5] text-[#239B75] border-[#B7EDD7]'
          : 'bg-[#FFF8EB] text-[#E5A33D] border-[#FCE2B6]'}"
      >
        <span class="relative flex h-2 w-2">
          {#if feedStatus.connected || feedStatus.mode === 'simulation'}
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#239B75] opacity-75"></span>
          {/if}
          <span class="relative inline-flex rounded-full h-2 w-2 {feedStatus.connected || feedStatus.mode === 'simulation' ? 'bg-[#239B75]' : 'bg-[#E5A33D]'}"></span>
        </span>
        <span class="font-semibold text-[10.5px] tracking-wider uppercase">
          {feedStatus.mode === 'simulation'
            ? 'Simulation'
            : feedStatus.connected
            ? feedStatus.mode === 'websocket'
              ? 'Live WS'
              : 'Polling'
            : 'Idle'}
        </span>
      </div>
    </div>

    <!-- Center Metrics Pills (Desktop / Tablet) -->
    <div class="hidden lg:flex items-center gap-2.5 text-xs font-mono">
      <div class="px-3 py-1.5 rounded-lg bg-[#F4F7FA] border border-[#E3EAF0] text-[#263747] flex items-center gap-1.5">
        <span class="text-[#718096]">Active:</span>
        <strong class="text-[#168AAD]">{aircraftList.length} Aircraft</strong>
      </div>

      <div class="px-3 py-1.5 rounded-lg bg-[#F4F7FA] border border-[#E3EAF0] text-[#263747] flex items-center gap-1.5">
        <span class="text-[#718096]">Nearest:</span>
        <strong class="text-[#239B75]">
          {nearestDistanceNm !== null && nearestDistanceNm < 9999 ? `${nearestDistanceNm.toFixed(1)} NM` : '--'}
        </strong>
      </div>

      <div class="px-3 py-1.5 rounded-lg bg-[#F4F7FA] border border-[#E3EAF0] text-[#718096] flex items-center gap-1.5 truncate max-w-xs" title={receiver.name}>
        <span>Antenna:</span>
        <span class="text-[#263747] font-medium truncate">{receiver.name.split(' ')[0]}</span>
      </div>
    </div>

    <!-- Right Quick Controls & Settings Button -->
    <div class="flex items-center gap-2">
      <!-- Quick Demo / Simulation Switch -->
      <button
        onclick={() => handleToggleSimulation(feedStatus.mode !== 'simulation')}
        class="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono border transition
          {feedStatus.mode === 'simulation'
            ? 'bg-[#EBF5F8] text-[#168AAD] border-[#B8DEEB] font-bold'
            : 'bg-white text-[#718096] border-[#E3EAF0] hover:text-[#263747] hover:border-slate-300'}"
        title="Toggle Simulated Air Traffic"
      >
        <span class="w-1.5 h-1.5 rounded-full {feedStatus.mode === 'simulation' ? 'bg-[#168AAD]' : 'bg-slate-300'}"></span>
        {feedStatus.mode === 'simulation' ? 'Simulation Active' : 'Demo Traffic'}
      </button>

      <!-- Data Source / Receiver Configuration Button -->
      <button
        onclick={() => (isSettingsOpen = true)}
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F4F7FA] hover:bg-[#EBF5F8] text-[#263747] hover:text-[#168AAD] border border-[#E3EAF0] hover:border-[#B8DEEB] text-xs font-medium transition shadow-2xs active:scale-95"
        title="Configure Data Source & Ground Receiver"
        aria-label="Settings"
      >
        <svg class="w-4 h-4 text-[#168AAD]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <circle cx="12" cy="12" r="3" stroke-width="1.8" />
        </svg>
        <span class="hidden sm:inline font-mono">Feed Settings</span>
      </button>
    </div>
  </header>

  <!-- Middle Work Area (Sidebar + Map) -->
  <div class="flex-1 relative flex overflow-hidden">
    <!-- Left Aircraft Sidebar (Responsive drawer on mobile, static column on desktop) -->
    <div
      class="fixed md:static inset-y-0 left-0 z-30 transform transition-transform duration-300 ease-in-out md:translate-x-0 {isSidebarOpenMobile ? 'translate-x-0' : '-translate-x-full'} h-full"
    >
      <Sidebar
        aircraft={aircraftList}
        {selectedPlane}
        {feedStatus}
        {receiver}
        {mapLayer}
        onSelectPlane={handleSelectPlane}
        onOpenSettings={() => (isSettingsOpen = true)}
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
        class="md:hidden fixed inset-0 bg-[#263747]/40 z-20 backdrop-blur-2xs"
        aria-label="Close Sidebar"
      ></div>
    {/if}

    <!-- Main Map Canvas -->
    <main class="flex-1 relative h-full w-full bg-[#EAF0F4]">
      <RadarMap
        aircraft={aircraftList}
        {selectedPlane}
        {receiver}
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
        <div class="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-4 py-2.5 rounded-xl bg-white border border-[#E5A33D] text-[#263747] text-xs font-sans shadow-lg flex items-center gap-2.5">
          <span class="text-base text-[#E5A33D]">⚠️</span>
          <span>{feedStatus.error}</span>
          <button
            onclick={() => (isSettingsOpen = true)}
            class="text-[#168AAD] hover:underline font-bold ml-1 font-mono"
          >
            Check Settings
          </button>
        </div>
      {/if}
    </main>
  </div>

  <!-- Bottom Status Bar -->
  <footer class="h-7 bg-white border-t border-[#E3EAF0] px-4 flex items-center justify-between text-[11px] font-mono text-[#718096] shrink-0 z-20">
    <div class="flex items-center gap-4">
      <div class="flex items-center gap-1.5">
        <span class="w-1.5 h-1.5 rounded-full bg-[#168AAD]"></span>
        <span>Station: <strong class="text-[#263747]">{receiver.name}</strong> ({formatCoords(receiver.lat, receiver.lon)})</span>
      </div>
      <div class="hidden md:inline text-[#CBD5E1]">|</div>
      <div class="hidden md:flex items-center gap-1">
        <span>Tracked:</span>
        <strong class="text-[#168AAD]">{aircraftList.length}</strong>
      </div>
    </div>

    <div class="flex items-center gap-4">
      <div class="hidden sm:flex items-center gap-1">
        <span>Throughput:</span>
        <strong class="text-[#263747]">{feedStatus.totalMessagesReceived.toLocaleString()} msgs</strong>
      </div>
      <div class="hidden sm:inline text-[#CBD5E1]">|</div>
      <div class="flex items-center gap-1">
        <span>Updated:</span>
        <strong class="text-[#263747]">{secondsAgo !== null ? `${secondsAgo}s ago` : 'Waiting'}</strong>
      </div>
    </div>
  </footer>

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
