<script lang="ts">
  import type { Aircraft } from '../types/aircraft';
  import { formatAltitude, formatSpeed, formatCoords } from '../utils/geo';

  interface Props {
    plane: Aircraft | null;
    onClose: () => void;
  }

  let { plane, onClose }: Props = $props();
</script>

{#if plane}
  <div class="p-4 bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-2xl shadow-2xl text-slate-200">
    <!-- Header -->
    <div class="flex items-start justify-between border-b border-slate-800 pb-3 mb-3">
      <div class="flex items-center gap-3">
        <div
          class="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-2xl border border-slate-700 shadow-inner"
          style="transform: rotate({Math.round(plane.heading)}deg);"
        >
          ✈️
        </div>
        <div>
          <h2 class="text-lg font-bold font-mono tracking-wider text-white flex items-center gap-2">
            {plane.callsign}
            <span class="text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800">
              {plane.hex}
            </span>
          </h2>
          <p class="text-xs text-slate-400 font-mono">
            Pos: {formatCoords(plane.lat, plane.lon)}
          </p>
        </div>
      </div>

      <button
        onclick={onClose}
        class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
        aria-label="Close"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Detailed Flight Data Grid -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-3 font-mono text-xs">
      <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
        <span class="text-slate-500 block text-[10px] uppercase">Altitude</span>
        <span class="text-cyan-400 font-bold text-sm">{formatAltitude(plane.altitude)}</span>
        {#if plane.verticalRate}
          <span class="text-[10px] block {plane.verticalRate > 0 ? 'text-emerald-400' : 'text-rose-400'}">
            {plane.verticalRate > 0 ? '+' : ''}{plane.verticalRate} fpm
          </span>
        {/if}
      </div>

      <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
        <span class="text-slate-500 block text-[10px] uppercase">Speed</span>
        <span class="text-white font-bold text-sm">{formatSpeed(plane.speed)}</span>
        <span class="text-[10px] text-slate-400 block">{Math.round(plane.speed * 1.852)} km/h</span>
      </div>

      <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
        <span class="text-slate-500 block text-[10px] uppercase">Track / Heading</span>
        <span class="text-white font-bold text-sm">{Math.round(plane.heading)}°</span>
        <span class="text-[10px] text-slate-400 block">Magnetic track</span>
      </div>

      <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
        <span class="text-slate-500 block text-[10px] uppercase">Range & Bearing</span>
        <span class="text-amber-400 font-bold text-sm">
          {plane.distanceNm !== undefined ? `${plane.distanceNm.toFixed(1)} NM` : '--'}
        </span>
        <span class="text-[10px] text-slate-400 block">
          BRG {plane.bearingDeg !== undefined ? `${Math.round(plane.bearingDeg)}°` : '--'}
        </span>
      </div>
    </div>

    <!-- Secondary Meta -->
    <div class="flex items-center justify-between text-[11px] font-mono text-slate-400 bg-slate-950/40 p-2 rounded-lg border border-slate-800/80">
      <div class="flex gap-4">
        <span>Squawk: <strong class="text-slate-200">{plane.squawk || 'None'}</strong></span>
        <span>Points: <strong class="text-slate-200">{plane.trail?.length ?? 1}</strong></span>
      </div>

      <div class="flex gap-2">
        <a
          href="https://www.flightradar24.com/{plane.callsign}"
          target="_blank"
          rel="noopener noreferrer"
          class="text-cyan-400 hover:text-cyan-300 hover:underline flex items-center gap-1"
        >
          Flightradar24 ↗
        </a>
      </div>
    </div>
  </div>
{/if}
