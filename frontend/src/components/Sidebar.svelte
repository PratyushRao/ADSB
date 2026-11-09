<script lang="ts">
  import type { Aircraft, FeedStatus, ReceiverLocation } from '../types/aircraft';
  import AircraftCard from './AircraftCard.svelte';

  interface Props {
    aircraft: Aircraft[];
    selectedPlane: Aircraft | null;
    feedStatus: FeedStatus;
    receiver: ReceiverLocation;
    mapLayer: 'osm' | 'satellite' | 'dark';
    onSelectPlane: (plane: Aircraft | null) => void;
    onOpenSettings: () => void;
    onChangeMapLayer: (layer: 'osm' | 'satellite' | 'dark') => void;
  }

  let {
    aircraft,
    selectedPlane,
    feedStatus,
    receiver,
    mapLayer,
    onSelectPlane,
    onOpenSettings,
    onChangeMapLayer,
  }: Props = $props();

  let searchQuery = $state('');
  let sortBy = $state<'distance' | 'altitude' | 'speed' | 'callsign'>('distance');

  // Distances
  const distances = $derived(
    aircraft
      .map((a) => a.distanceNm)
      .filter((d): d is number => d !== undefined && !isNaN(d))
  );
  const nearestNm = $derived(distances.length > 0 ? Math.min(...distances) : null);

  // Filtered and sorted aircraft queue (search + sort)
  const filteredAircraft = $derived(
    aircraft
      .filter((plane) => {
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase().trim();
        const matchCallsign = plane.callsign.toLowerCase().includes(q);
        const matchHex = plane.hex.toLowerCase().includes(q);
        const matchOrigin =
          plane.route?.origin.iata?.toLowerCase().includes(q) ||
          plane.route?.origin.city?.toLowerCase().includes(q);
        const matchDest =
          plane.route?.destination.iata?.toLowerCase().includes(q) ||
          plane.route?.destination.city?.toLowerCase().includes(q);
        return matchCallsign || matchHex || matchOrigin || matchDest;
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

  function handleStripClick(plane: Aircraft) {
    if (selectedPlane?.hex === plane.hex) {
      onSelectPlane(null); // Click to collapse/deselect
    } else {
      onSelectPlane(plane);
    }
  }
</script>

<aside class="w-full md:w-96 lg:w-[410px] h-full flex flex-col bg-white/95 backdrop-blur-xl border-r border-[#E3EAF0]/90 text-[#263747] z-10 select-none">
  <!-- AIRSPACE DESK HEADER -->
  <div class="px-5 py-4 border-b border-[#E3EAF0]/80 bg-white/60">
    <div class="flex items-start justify-between">
      <div>
        <div class="flex items-center gap-2">
          <h2 class="font-sans font-medium text-sm text-[#263747]">
            Airspace Desk
          </h2>
          <span class="inline-flex items-center gap-1.5 text-xs font-sans text-[#718096]">
            <span class="w-1.5 h-1.5 rounded-full {feedStatus.connected || feedStatus.mode === 'simulation' ? 'bg-[#239B75] animate-pulse' : 'bg-[#E5A33D]'}"></span>
            {feedStatus.mode === 'simulation' ? 'Simulation' : feedStatus.connected ? 'Live Feed' : 'Idle'}
          </span>
        </div>
        <p class="text-xs text-[#718096] mt-0.5 font-sans font-normal">
          {receiver.name.split(' ')[0]} Station · 1090 MHz Mode S
        </p>
      </div>

      <!-- Settings Icon Button -->
      <button
        onclick={onOpenSettings}
        class="p-1.5 rounded-md hover:bg-slate-100 text-[#718096] hover:text-[#168AAD] transition"
        title="Configure ADS-B Feed & Antenna"
        aria-label="Settings"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <circle cx="12" cy="12" r="3" stroke-width="1.8" />
        </svg>
      </button>
    </div>

    <!-- Quiet Sector Overview Line -->
    <div class="mt-3 flex items-baseline justify-between text-xs">
      <div class="font-sans font-medium text-[#263747]">
        {aircraft.length} {aircraft.length === 1 ? 'Flight' : 'Flights'} in Sector
      </div>
      {#if nearestNm !== null}
        <div class="text-xs font-sans text-[#718096]">
          Nearest at <span class="text-[#239B75] font-mono font-medium tabular-nums">{nearestNm.toFixed(1)} NM</span>
        </div>
      {/if}
    </div>
  </div>

  <!-- SEARCH SECTION (Clean, Space-Efficient) -->
  <div class="px-5 py-3 border-b border-[#E3EAF0]/80 bg-white/40">
    <div class="relative">
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search callsign, hex, or route..."
        class="w-full pl-8 pr-7 py-2 rounded-lg bg-[#F8FAFC] border border-[#E3EAF0] font-sans text-xs text-[#263747] placeholder-[#718096] focus:outline-none focus:border-[#168AAD] focus:bg-white focus:ring-1 focus:ring-[#168AAD]/20 transition"
      />
      <svg class="w-3.5 h-3.5 text-[#718096] absolute left-2.5 top-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      {#if searchQuery}
        <button
          onclick={() => (searchQuery = '')}
          class="absolute right-2.5 top-2.5 text-[#718096] hover:text-[#263747] text-xs font-sans font-medium"
          aria-label="Clear search"
        >
          ✕
        </button>
      {/if}
    </div>
  </div>

  <!-- FLIGHT QUEUE HEADER & SORTING -->
  <div class="px-5 py-2.5 bg-[#F8FAFC]/80 border-b border-[#E3EAF0]/80 flex items-center justify-between text-xs font-sans text-[#718096]">
    <div>
      <span class="font-sans font-medium text-[#263747]">{filteredAircraft.length}</span>
      <span class="text-[#718096] font-sans font-normal">{filteredAircraft.length === 1 ? 'Flight' : 'Flights'}</span>
    </div>

    <!-- Quiet Sort Selector -->
    <div class="flex items-center gap-1.5 text-xs font-sans">
      <span class="text-[#718096] font-normal">Sort by</span>
      <select
        bind:value={sortBy}
        class="bg-transparent border-0 text-[#263747] font-sans font-medium text-xs focus:outline-none cursor-pointer hover:text-[#168AAD]"
      >
        <option value="distance">Distance</option>
        <option value="altitude">Altitude</option>
        <option value="speed">Speed</option>
        <option value="callsign">Callsign</option>
      </select>
    </div>
  </div>

  <!-- CONTINUOUS AIRCRAFT LIST (Reclaimed Vertical Space) -->
  <div class="flex-1 overflow-y-auto bg-white">
    {#if filteredAircraft.length > 0}
      {#each filteredAircraft as plane (plane.hex)}
        <AircraftCard
          {plane}
          isSelected={selectedPlane?.hex === plane.hex}
          onSelect={handleStripClick}
        />
      {/each}
    {:else}
      <!-- Human-Crafted Aviation Empty State -->
      <div class="h-64 flex flex-col items-center justify-center text-center px-6 py-8 text-[#718096]">
        <svg class="w-8 h-8 text-[#168AAD]/60 mb-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="9" stroke-width="1.5" stroke-dasharray="3 3" />
          <circle cx="12" cy="12" r="4" stroke-width="1.2" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 3v9l5 3" />
        </svg>
        <p class="font-sans font-medium text-xs text-[#263747] mb-1">
          {searchQuery ? 'No Matching Flights' : 'No Flights Detected in Sector'}
        </p>
        <p class="text-xs text-[#718096] font-sans font-normal max-w-[220px] leading-relaxed mb-3">
          {searchQuery
            ? 'Try broadening your search term.'
            : 'Listening for live 1090 MHz Mode S ADS-B transmissions on station antenna.'}
        </p>
        {#if searchQuery}
          <button
            onclick={() => (searchQuery = '')}
            class="text-xs font-sans font-medium text-[#168AAD] hover:underline"
          >
            Clear Search
          </button>
        {:else}
          <button
            onclick={onOpenSettings}
            class="text-xs font-sans font-medium text-[#168AAD] hover:underline"
          >
            Check Feed Settings →
          </button>
        {/if}
      </div>
    {/if}
  </div>

  <!-- BOTTOM MAP LAYER CONTROLS (Street, Satellite, Dark only) -->
  <div class="px-5 py-2.5 bg-[#F8FAFC] border-t border-[#E3EAF0]/80 flex items-center justify-between text-xs font-sans text-[#718096]">
    <div class="flex items-center gap-2">
      <span class="text-xs font-sans text-[#718096]">Map:</span>
      <div class="flex items-center gap-2 text-xs">
        <button
          onclick={() => onChangeMapLayer('osm')}
          class="transition font-sans font-medium {mapLayer === 'osm' ? 'text-[#168AAD]' : 'text-[#718096] hover:text-[#263747]'}"
        >
          Street
        </button>
        <span class="text-[#CBD5E1]">·</span>
        <button
          onclick={() => onChangeMapLayer('satellite')}
          class="transition font-sans font-medium {mapLayer === 'satellite' ? 'text-[#168AAD]' : 'text-[#718096] hover:text-[#263747]'}"
        >
          Satellite
        </button>
        <span class="text-[#CBD5E1]">·</span>
        <button
          onclick={() => onChangeMapLayer('dark')}
          class="transition font-sans font-medium {mapLayer === 'dark' ? 'text-[#168AAD]' : 'text-[#718096] hover:text-[#263747]'}"
        >
          Dark
        </button>
      </div>
    </div>
  </div>
</aside>
