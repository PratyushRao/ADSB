<script lang="ts">
  import type { Aircraft } from '../types/aircraft';
  import { formatAltitude, formatSpeed, formatCoords, formatHeading } from '../utils/geo';

  interface Props {
    plane: Aircraft | null;
    onClose: () => void;
  }

  let { plane, onClose }: Props = $props();

  const checkLabel = {
    plausible: '✓ Matches live position',
    'off-route': '⚠ Off reported route',
    reverse: '⚠ Opposite heading',
    unverified: 'Unverified route',
  } as const;

  const checkStyle = {
    plausible: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    'off-route': 'text-amber-700 bg-amber-50 border-amber-200',
    reverse: 'text-amber-700 bg-amber-50 border-amber-200',
    unverified: 'text-slate-600 bg-slate-100 border-slate-200',
  } as const;

  const code = (a: { iata?: string | null; icao?: string | null }) => a.iata || a.icao || '???';
</script>

{#if plane}
  <div class="glass-panel p-4 bg-white/95 backdrop-blur-md border border-[#E3EAF0] rounded-2xl shadow-xl text-[#263747] max-w-lg w-full select-none">
    <!-- Header (Prominent Aviation Identification) -->
    <div class="flex items-start justify-between border-b border-[#E3EAF0] pb-3.5 mb-3.5">
      <div class="flex items-center gap-3.5">
        <div
          class="w-12 h-12 rounded-xl bg-[#F0F8FA] border border-[#B8DEEB] flex items-center justify-center text-[#168AAD] shadow-2xs shrink-0"
          title="Track: {Math.round(plane.heading)}°"
        >
          <svg
            class="w-6 h-6 transition-transform duration-300"
            style="transform: rotate({Math.round(plane.heading)}deg);"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M12 2C11.4 2 11 2.5 11 3.2V8.5L3.5 13V15L11 12.8V18.2L8.5 20.2V22L12 21L15.5 22V20.2L13 18.2V12.8L20.5 15V13L13 8.5V3.2C13 2.5 12.6 2 12 2Z" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2.5">
            <h2 class="text-xl sm:text-2xl font-sans font-semibold text-[#263747] leading-none">
              {plane.callsign}
            </h2>
            <span class="text-xs font-mono font-normal px-2.5 py-0.5 rounded-md bg-[#F4F7FA] text-[#168AAD] border border-[#E3EAF0] leading-none tabular-nums">
              {plane.hex}
            </span>
            {#if plane.category}
              <span class="text-xs font-sans font-normal px-2 py-0.5 rounded bg-slate-100 text-[#718096] border border-slate-200 leading-none">
                Cat {plane.category}
              </span>
            {/if}
          </div>
          <p class="text-xs text-[#718096] font-mono font-normal mt-1.5 tabular-nums">
            Pos: {formatCoords(plane.lat, plane.lon)}
          </p>
        </div>
      </div>

      <button
        onclick={onClose}
        class="text-[#718096] hover:text-[#263747] p-2 rounded-xl hover:bg-[#F4F7FA] transition"
        title="Close Inspector"
        aria-label="Close"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Route (when looked up from callsign and cross-checked against live position) -->
    {#if plane.route}
      {@const r = plane.route}
      <div class="mb-3 p-3 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0]">
        <div class="flex items-center justify-between text-xs font-sans font-medium text-[#718096] mb-2">
          <span>Flight {r.flight}{r.airline ? ` · ${r.airline}` : ''}</span>
          <span class="px-2 py-0.5 rounded-full border text-xs font-sans font-medium {checkStyle[r.check]}" title={r.checkDetail}>
            {checkLabel[r.check]}
          </span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <div class="flex-1 min-w-0">
            <div class="text-lg font-sans font-semibold text-[#263747]">{code(r.origin)}</div>
            <div class="text-xs font-sans font-normal text-[#718096] truncate" title={r.origin.name ?? ''}>
              {r.origin.city || r.origin.name || 'Origin Airport'}
            </div>
          </div>
          <div class="flex flex-col items-center px-2">
            <span class="text-[#168AAD] text-xs font-sans font-medium">✈ ──▶</span>
            <span class="text-xs font-sans font-normal text-[#718096]">Direct</span>
          </div>
          <div class="flex-1 min-w-0 text-right">
            <div class="text-lg font-sans font-semibold text-[#263747]">{code(r.destination)}</div>
            <div class="text-xs font-sans font-normal text-[#718096] truncate" title={r.destination.name ?? ''}>
              {r.destination.city || r.destination.name || 'Dest Airport'}
            </div>
          </div>
        </div>
        <div class="mt-2 pt-2 border-t border-[#E3EAF0] text-xs font-sans text-[#718096] flex items-center justify-between">
          <span>{r.checkDetail}</span>
          <span class="font-mono text-xs text-[#718096]/80">src: {r.source}</span>
        </div>
      </div>
    {/if}

    <!-- Unified Telemetry Container (Single surface with subtle vertical dividers) -->
    <div class="mb-3 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] shadow-2xs overflow-hidden">
      <div class="grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 divide-[#E3EAF0] sm:divide-x sm:divide-[#E3EAF0]">
        <!-- 1. Altitude -->
        <div class="px-3.5 py-2.5 flex flex-col justify-between">
          <span class="text-[#718096] text-xs font-sans font-normal">
            Altitude
          </span>
          <div class="my-0.5">
            <span class="text-[#168AAD] font-mono font-medium text-sm tabular-nums block">
              {formatAltitude(plane.altitude)}
            </span>
          </div>
          <div class="text-xs leading-tight">
            {#if plane.verticalRate && Math.abs(plane.verticalRate) > 100}
              <span class="font-mono font-medium tabular-nums {plane.verticalRate > 0 ? 'text-[#239B75]' : 'text-[#D97706]'}">
                {plane.verticalRate > 0 ? '▲ +' : '▼ '}{plane.verticalRate} fpm
              </span>
            {:else}
              <span class="text-[#718096] font-sans font-normal">Level flight</span>
            {/if}
          </div>
        </div>

        <!-- 2. Ground Speed -->
        <div class="px-3.5 py-2.5 flex flex-col justify-between">
          <span class="text-[#718096] text-xs font-sans font-normal">
            Ground Speed
          </span>
          <div class="my-0.5">
            <span class="text-[#263747] font-mono font-medium text-sm tabular-nums block">
              {formatSpeed(plane.speed)}
            </span>
          </div>
          <div class="text-xs font-mono font-normal text-[#718096] tabular-nums leading-tight">
            {Math.round(plane.speed * 1.852)} km/h
          </div>
        </div>

        <!-- 3. Track / Heading -->
        <div class="px-3.5 py-2.5 flex flex-col justify-between">
          <span class="text-[#718096] text-xs font-sans font-normal">
            Track / Heading
          </span>
          <div class="my-0.5">
            <span class="text-[#263747] font-mono font-medium text-sm tabular-nums block truncate">
              {formatHeading(plane.heading)}
            </span>
          </div>
          <div class="text-xs font-sans font-normal text-[#718096] leading-tight">
            True track
          </div>
        </div>

        <!-- 4. Range & Bearing -->
        <div class="px-3.5 py-2.5 flex flex-col justify-between">
          <span class="text-[#718096] text-xs font-sans font-normal">
            Range & Bearing
          </span>
          <div class="my-0.5">
            <span class="text-[#239B75] font-mono font-medium text-sm tabular-nums block">
              {plane.distanceNm !== undefined ? `${plane.distanceNm.toFixed(1)} NM` : '--'}
            </span>
          </div>
          <div class="text-xs font-mono font-normal text-[#718096] tabular-nums leading-tight">
            {plane.bearingDeg !== undefined ? `BRG ${Math.round(plane.bearingDeg)}°` : '--'}
          </div>
        </div>
      </div>
    </div>

    <!-- Secondary Meta Strip -->
    <div class="flex items-center justify-between text-xs font-sans text-[#718096] bg-[#F4F7FA] px-3 py-2 rounded-xl border border-[#E3EAF0]">
      <div class="flex gap-4">
        <span>Squawk: <strong class="text-[#263747] font-mono font-normal tabular-nums">{plane.squawk || 'None'}</strong></span>
        <span>Points: <strong class="text-[#263747] font-mono font-normal tabular-nums">{plane.trail?.length ?? 1}</strong></span>
      </div>
      <div>
        <span>Seen: <strong class="text-[#263747] font-mono font-normal tabular-nums">{plane.seen}s ago</strong></span>
      </div>
    </div>
  </div>
{/if}
