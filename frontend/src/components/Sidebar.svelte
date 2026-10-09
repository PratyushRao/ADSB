<script lang="ts">
  import type { Aircraft, FeedStatus, ReceiverLocation } from '../types/aircraft';
  import AircraftCard from './AircraftCard.svelte';

  interface Props {
    aircraft: Aircraft[];
    selectedPlane: Aircraft | null;
    feedStatus: FeedStatus;
    receiver: ReceiverLocation;
    showRangeRings: boolean;
    showTrails: boolean;
    mapLayer: 'dark' | 'osm' | 'satellite';
    onSelectPlane: (plane: Aircraft | null) => void;
    onOpenSettings: () => void;
    onToggleRangeRings: () => void;
    onToggleTrails: () => void;
    onChangeMapLayer: (layer: 'dark' | 'osm' | 'satellite') => void;
  }

  let {
    aircraft,
    selectedPlane,
    feedStatus,
    receiver,
    showRangeRings,
    showTrails,
    mapLayer,
    onSelectPlane,
    onOpenSettings,
    onToggleRangeRings,
    onToggleTrails,
    onChangeMapLayer,
  }: Props = $props();

  let searchQuery = $state('');
  let sortBy = $state<'distance' | 'altitude' | 'speed' | 'callsign'>('distance');

  // Filter and sort aircraft
  const filteredAircraft = $derived(
    aircraft
      .filter((plane) => {
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase().trim();
        return (
          plane.callsign.toLowerCase().includes(q) ||
          plane.hex.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        if (sortBy === 'distance') {
          return (a.distanceNm ?? 99999) - (b.distanceNm ?? 99999);
        }
        if (sortBy === 'altitude') {
          return b.altitude - a.altitude;
        }
        if (sortBy === 'speed') {
          return b.speed - a.speed;
        }
        return a.callsign.localeCompare(b.callsign);
      })
  );

  const closestDistance = $derived(
    aircraft.length > 0
      ? Math.min(...aircraft.map((a) => a.distanceNm ?? 99999))
      : null
  );
</script>

<aside class="w-full md:w-96 lg:w-[410px] h-full flex flex-col bg-slate-950/95 border-r border-slate-800 text-slate-100 z-10 shadow-2xl backdrop-blur-xl">
  <!-- Top App Bar -->
  <div class="p-4 border-b border-slate-800/80 bg-slate-950/60 flex items-center justify-between">
    <div class="flex items-center gap-2.5">
      <div class="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-lg shadow-inner">
        ✈️
      </div>
      <div>
        <h1 class="text-base font-bold font-mono tracking-wider text-white leading-tight">
          ADSB RADAR
        </h1>
        <div class="flex items-center gap-1.5 mt-0.5">
          <span
            class="w-2 h-2 rounded-full {feedStatus.connected || feedStatus.mode === 'simulation' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}"
          ></span>
          <span class="text-[10px] font-mono uppercase tracking-wider text-slate-400">
            {feedStatus.mode === 'simulation'
              ? 'SIMULATION'
              : feedStatus.connected
              ? 'CONNECTED'
              : 'IDLE'}
          </span>
        </div>
      </div>
    </div>

    <!-- Data Source Config Button -->
    <button
      onclick={onOpenSettings}
      class="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-cyan-400 hover:text-cyan-300 transition shadow-sm active:scale-95"
      title="Configure Data Source & Receiver"
      aria-label="Settings"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <circle cx="12" cy="12" r="3" stroke-width="2" />
      </svg>
    </button>
  </div>

  <!-- Radar Telemetry Summary Bar -->
  <div class="grid grid-cols-3 gap-2 px-4 py-2.5 bg-slate-900/40 border-b border-slate-800/60 font-mono text-center">
    <div class="p-1.5 rounded-lg bg-slate-950/60 border border-slate-800">
      <div class="text-[9px] text-slate-400 uppercase tracking-wider">Tracks</div>
      <div class="text-base font-bold text-cyan-400">{aircraft.length}</div>
    </div>
    <div class="p-1.5 rounded-lg bg-slate-950/60 border border-slate-800">
      <div class="text-[9px] text-slate-400 uppercase tracking-wider">Nearest</div>
      <div class="text-base font-bold text-amber-400">
        {closestDistance !== null && closestDistance < 9999 ? `${closestDistance.toFixed(1)} NM` : '--'}
      </div>
    </div>
    <div class="p-1.5 rounded-lg bg-slate-950/60 border border-slate-800">
      <div class="text-[9px] text-slate-400 uppercase tracking-wider">Receiver</div>
      <div class="text-xs font-semibold text-slate-200 truncate mt-0.5" title={receiver.name}>
        {receiver.name.split(' ')[0]}
      </div>
    </div>
  </div>

  <!-- Search & Sorting Filters -->
  <div class="p-3 border-b border-slate-800/60 space-y-2">
    <div class="relative">
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search flight callsign or hex..."
        class="w-full pl-9 pr-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 font-mono text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
      />
      <svg class="w-4 h-4 text-slate-400 absolute left-3 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      {#if searchQuery}
        <button
          onclick={() => (searchQuery = '')}
          class="absolute right-2.5 top-2 text-slate-400 hover:text-white"
        >
          ✕
        </button>
      {/if}
    </div>

    <!-- Map controls and sort options -->
    <div class="flex items-center justify-between text-xs font-mono text-slate-400 pt-1">
      <div class="flex items-center gap-1.5">
        <span>Sort:</span>
        <select
          bind:value={sortBy}
          class="bg-slate-900 border border-slate-700/80 rounded-lg px-2 py-0.5 text-slate-200 text-xs font-mono focus:outline-none focus:border-cyan-500"
        >
          <option value="distance">Distance</option>
          <option value="altitude">Altitude</option>
          <option value="speed">Speed</option>
          <option value="callsign">Callsign</option>
        </select>
      </div>

      <div class="flex items-center gap-2">
        <button
          onclick={onToggleRangeRings}
          class="px-2 py-0.5 rounded text-[10px] border transition {showRangeRings ? 'bg-cyan-950 text-cyan-300 border-cyan-700' : 'bg-slate-900 text-slate-400 border-slate-700'}"
          title="Toggle Range Rings"
        >
          Rings
        </button>
        <button
          onclick={onToggleTrails}
          class="px-2 py-0.5 rounded text-[10px] border transition {showTrails ? 'bg-cyan-950 text-cyan-300 border-cyan-700' : 'bg-slate-900 text-slate-400 border-slate-700'}"
          title="Toggle Flight Trails"
        >
          Trails
        </button>
      </div>
    </div>
  </div>

  <!-- Aircraft Cards Scroll List -->
  <div class="flex-1 overflow-y-auto p-3 space-y-2">
    {#if filteredAircraft.length > 0}
      {#each filteredAircraft as plane (plane.hex)}
        <AircraftCard
          {plane}
          isSelected={selectedPlane?.hex === plane.hex}
          onSelect={onSelectPlane}
        />
      {/each}
    {:else}
      <div class="h-64 flex flex-col items-center justify-center text-center p-6 text-slate-400">
        <div class="text-3xl mb-2">🛰️</div>
        <p class="font-mono text-xs font-semibold text-slate-300 mb-1">No Aircraft In Range</p>
        <p class="text-[11px] text-slate-500 mb-4 max-w-xs">
          Waiting for ADS-B messages from your backend endpoint or JSON feed.
        </p>
        <button
          onclick={onOpenSettings}
          class="px-3.5 py-1.5 rounded-xl text-xs font-mono bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 transition"
        >
          Configure Data Source
        </button>
      </div>
    {/if}
  </div>

  <!-- Map Layer Selector Footer -->
  <div class="p-3 bg-slate-950/80 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
    <span class="text-slate-500">Base Map:</span>
    <div class="flex gap-1.5">
      <button
        onclick={() => onChangeMapLayer('dark')}
        class="px-2 py-1 rounded-lg border text-[11px] transition {mapLayer === 'dark' ? 'bg-cyan-950 text-cyan-300 border-cyan-500' : 'bg-slate-900 text-slate-400 border-slate-700'}"
      >
        Dark Radar
      </button>
      <button
        onclick={() => onChangeMapLayer('osm')}
        class="px-2 py-1 rounded-lg border text-[11px] transition {mapLayer === 'osm' ? 'bg-cyan-950 text-cyan-300 border-cyan-500' : 'bg-slate-900 text-slate-400 border-slate-700'}"
      >
        Street
      </button>
      <button
        onclick={() => onChangeMapLayer('satellite')}
        class="px-2 py-1 rounded-lg border text-[11px] transition {mapLayer === 'satellite' ? 'bg-cyan-950 text-cyan-300 border-cyan-500' : 'bg-slate-900 text-slate-400 border-slate-700'}"
      >
        Satellite
      </button>
    </div>
  </div>
</aside>
