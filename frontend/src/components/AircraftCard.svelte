<script lang="ts">
  import type { Aircraft } from '../types/aircraft';
  import { formatAltitude, formatSpeed } from '../utils/geo';

  interface Props {
    plane: Aircraft;
    isSelected: boolean;
    onSelect: (plane: Aircraft) => void;
  }

  let { plane, isSelected, onSelect }: Props = $props();

  function getAltitudeBadgeColor(altitudeFeet: number): string {
    if (altitudeFeet < 5000) return 'text-sky-400 bg-sky-950/60 border-sky-800/60';
    if (altitudeFeet < 15000) return 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60';
    if (altitudeFeet < 25000) return 'text-amber-400 bg-amber-950/60 border-amber-800/60';
    if (altitudeFeet < 35000) return 'text-orange-400 bg-orange-950/60 border-orange-800/60';
    return 'text-rose-400 bg-rose-950/60 border-rose-800/60';
  }
</script>

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(plane)}
  onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(plane)}
  class="w-full text-left p-3 rounded-xl transition-all duration-200 border cursor-pointer select-none
    {isSelected
      ? 'bg-cyan-950/40 border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.25)]'
      : 'bg-slate-900/60 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700'}"
>
  <div class="flex items-center justify-between gap-2 mb-1.5">
    <!-- Callsign & Plane Icon -->
    <div class="flex items-center gap-2 min-w-0">
      <div
        class="w-7 h-7 rounded-lg flex items-center justify-center text-sm bg-slate-800/90 border border-slate-700/60"
        style="transform: rotate({Math.round(plane.heading)}deg);"
      >
        ✈️
      </div>
      <div class="truncate">
        <div class="font-mono font-bold text-sm tracking-wider {isSelected ? 'text-cyan-300' : 'text-slate-100'}">
          {plane.callsign}
        </div>
        <div class="text-[10px] font-mono text-slate-400">
          HEX: {plane.hex}
        </div>
      </div>
    </div>

    <!-- Altitude Badge -->
    <div class="flex flex-col items-end">
      <span class="px-2 py-0.5 rounded text-[11px] font-mono font-semibold border {getAltitudeBadgeColor(plane.altitude)}">
        {formatAltitude(plane.altitude)}
        {#if (plane.verticalRate ?? 0) > 200}
          <span class="text-emerald-400 ml-0.5">▲</span>
        {:else if (plane.verticalRate ?? 0) < -200}
          <span class="text-rose-400 ml-0.5">▼</span>
        {/if}
      </span>
    </div>
  </div>

  <!-- Telemetry Metrics Grid -->
  <div class="grid grid-cols-3 gap-2 pt-1 border-t border-slate-800/60 text-[11px] font-mono">
    <div>
      <span class="text-slate-500 block text-[9px] uppercase tracking-wider">Speed</span>
      <span class="text-slate-200 font-medium">{formatSpeed(plane.speed)}</span>
    </div>
    <div>
      <span class="text-slate-500 block text-[9px] uppercase tracking-wider">Track</span>
      <span class="text-slate-200 font-medium">{Math.round(plane.heading)}°</span>
    </div>
    <div class="text-right">
      <span class="text-slate-500 block text-[9px] uppercase tracking-wider">Distance</span>
      <span class="text-cyan-400 font-medium">
        {plane.distanceNm !== undefined ? `${plane.distanceNm.toFixed(1)} NM` : '--'}
      </span>
    </div>
  </div>
</div>
