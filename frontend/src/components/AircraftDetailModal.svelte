<script lang="ts">
  import type { Aircraft } from '../types/aircraft';
  import { formatAltitude, formatSpeed, formatCoords } from '../utils/geo';

  interface Props {
    plane: Aircraft | null;
    onClose: () => void;
  }

  let { plane, onClose }: Props = $props();

  const checkLabel = {
    plausible: '✓ matches position',
    'off-route': '⚠ off route',
    reverse: '⚠ opposite direction',
    unverified: 'unverified',
  } as const;
  const checkStyle = {
    plausible: 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60',
    'off-route': 'text-amber-400 bg-amber-950/60 border-amber-800/60',
    reverse: 'text-amber-400 bg-amber-950/60 border-amber-800/60',
    unverified: 'text-slate-400 bg-slate-900 border-slate-700',
  } as const;
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

    <!-- Route (looked up from the callsign, cross-checked against the live position) -->
    {#if plane.route}
      {@const r = plane.route}
      <div class="mb-3 p-3 rounded-xl bg-slate-950/70 border border-slate-800 font-mono">
        <div class="flex items-center justify-between text-[10px] uppercase text-slate-500 mb-2">
          <span>Route · {r.flight}{r.airline ? ` · ${r.airline}` : ''}</span>
          <span class="px-2 py-0.5 rounded-full border normal-case {checkStyle[r.check]}" title={r.checkDetail}>
            {checkLabel[r.check]}
          </span>
        </div>
        <div class="flex items-center gap-3">
          <div class="flex-1 min-w-0">
            <div class="text-xl font-bold text-white">{r.origin.iata || r.origin.icao || '???'}</div>
            <div class="text-[10px] text-slate-400 truncate" title={r.origin.name ?? ''}>{r.origin.city || r.origin.name || ''}</div>
          </div>
          <div class="text-cyan-400 text-lg">✈ →</div>
          <div class="flex-1 min-w-0 text-right">
            <div class="text-xl font-bold text-white">{r.destination.iata || r.destination.icao || '???'}</div>
            <div class="text-[10px] text-slate-400 truncate" title={r.destination.name ?? ''}>{r.destination.city || r.destination.name || ''}</div>
          </div>
        </div>
        <div class="mt-2 text-[10px] text-slate-500">{r.checkDetail} · route data: {r.source}</div>
      </div>
    {:else if plane.callsign !== plane.hex}
      <div class="mb-3 p-2 rounded-lg bg-slate-950/40 border border-slate-800/80 text-[11px] font-mono text-slate-500">
        Route: not found for callsign {plane.callsign}
      </div>
    {/if}

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
        {#if plane.category}<span>Cat: <strong class="text-slate-200">{plane.category}</strong></span>{/if}
      </div>
    </div>
  </div>
{/if}
