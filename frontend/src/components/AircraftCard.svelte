<script lang="ts">
  import type { Aircraft } from '../types/aircraft';
  import { formatAltitude, formatSpeed, formatCoords, formatHeading } from '../utils/geo';

  interface Props {
    plane: Aircraft;
    isSelected: boolean;
    onSelect: (plane: Aircraft) => void;
  }

  let { plane, isSelected, onSelect }: Props = $props();

  const code = (a: { iata?: string | null; icao?: string | null }) => a.iata || a.icao || '???';

  // Altitude category color indicator
  function getAltitudeTone(alt: number) {
    if (alt >= 25000) return { bar: 'bg-indigo-500', text: 'text-indigo-900', label: 'Cruise' };
    if (alt >= 10000) return { bar: 'bg-blue-500', text: 'text-blue-900', label: 'Mid' };
    if (alt >= 3000) return { bar: 'bg-[#168AAD]', text: 'text-[#168AAD]', label: 'Terminal' };
    return { bar: 'bg-emerald-600', text: 'text-emerald-900', label: 'Approach' };
  }

  const tone = $derived(getAltitudeTone(plane.altitude));
  const isClimbing = $derived((plane.verticalRate ?? 0) > 200);
  const isDescending = $derived((plane.verticalRate ?? 0) < -200);
</script>

<!-- Human-Crafted Aviation Flight Strip Row -->
<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(plane)}
  onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(plane)}
  class="group relative w-full text-left transition-all duration-150 cursor-pointer select-none border-b border-[#E3EAF0]/70
    {isSelected
      ? 'bg-[#F0F8FA] border-b-[#B8DEEB]'
      : 'bg-white hover:bg-[#F8FAFC]'}"
>
  <!-- Subtle Left Indicator Bar -->
  <div
    class="absolute left-0 top-0 bottom-0 w-[3px] transition-all
      {isSelected ? 'bg-[#168AAD] opacity-100' : 'bg-transparent group-hover:bg-[#CBD5E1]'}"
  ></div>

  <!-- Main Flight Row Container with Generous Whitespace -->
  <div class="pl-4 pr-3.5 py-3">
    <!-- Row 1: Identification & Altitude -->
    <div class="flex items-baseline justify-between gap-3">
      <!-- Left: Callsign & Micro Directional Silhouette -->
      <div class="flex items-center gap-2 min-w-0">
        <!-- Directional Vector Icon (Rotated to Heading) -->
        <svg
          class="w-3.5 h-3.5 shrink-0 transition-transform duration-300 {isSelected ? 'text-[#168AAD]' : 'text-[#718096] group-hover:text-[#168AAD]'}"
          style="transform: rotate({Math.round(plane.heading)}deg);"
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M12 2C11.4 2 11 2.5 11 3.2V8.5L3.5 13V15L11 12.8V18.2L8.5 20.2V22L12 21L15.5 22V20.2L13 18.2V12.8L20.5 15V13L13 8.5V3.2C13 2.5 12.6 2 12 2Z" />
        </svg>

        <span class="font-sans font-semibold text-sm text-[#263747] {isSelected ? 'text-[#168AAD]' : ''}">
          {plane.callsign}
        </span>

        <span class="text-xs font-mono text-[#718096]">
          {plane.hex}
        </span>

        {#if plane.category}
          <span class="text-xs font-sans font-normal text-[#718096]/80 hidden sm:inline">
            · Cat {plane.category}
          </span>
        {/if}
      </div>

      <!-- Right: Altitude & Vertical Rate -->
      <div class="flex items-baseline gap-1.5 shrink-0 text-right">
        <span class="font-mono font-medium text-sm text-[#263747] tabular-nums">
          {formatAltitude(plane.altitude)}
        </span>

        {#if isClimbing}
          <span class="text-xs font-mono font-medium text-[#239B75] tabular-nums flex items-center">
            ↑{plane.verticalRate}
          </span>
        {:else if isDescending}
          <span class="text-xs font-mono font-medium text-[#D97706] tabular-nums flex items-center">
            ↓{Math.abs(plane.verticalRate ?? 0)}
          </span>
        {/if}
      </div>
    </div>

    <!-- Row 2: Route / Origin-Destination (If Available) -->
    {#if plane.route}
      <div class="mt-1 flex items-center gap-1.5 text-xs text-[#718096]">
        <span class="font-sans font-medium text-[#263747]">{code(plane.route.origin)}</span>
        <span class="text-[#CBD5E1] text-xs">→</span>
        <span class="font-sans font-medium text-[#263747]">{code(plane.route.destination)}</span>
        {#if plane.route.airline}
          <span class="text-xs font-sans font-normal text-[#718096] truncate">· {plane.route.airline}</span>
        {/if}
        {#if plane.route.check === 'off-route' || plane.route.check === 'reverse'}
          <span class="text-[#E5A33D] font-sans font-medium text-xs" title={plane.route.checkDetail}>⚠</span>
        {/if}
      </div>
    {/if}

    <!-- Row 3: Telemetry Data Line (Clean, Unboxed Editorial Spacing) -->
    <div class="mt-1.5 flex items-center gap-3 text-xs font-mono text-[#718096]">
      <div>
        <span class="text-[#263747] font-medium tabular-nums">{formatSpeed(plane.speed)}</span>
      </div>
      <div class="text-[#CBD5E1]">·</div>
      <div>
        <span class="text-[#263747] font-medium tabular-nums">{Math.round(plane.heading)}°</span>
      </div>
      <div class="text-[#CBD5E1]">·</div>
      <div>
        <span class="text-[#168AAD] font-medium tabular-nums">
          {plane.distanceNm !== undefined ? `${plane.distanceNm.toFixed(1)} NM` : '--'}
        </span>
      </div>
      {#if !plane.route && plane.squawk}
        <div class="text-[#CBD5E1]">·</div>
        <div class="tabular-nums">
          SQ {plane.squawk}
        </div>
      {/if}
    </div>

    <!-- Inline Expanded Telemetry Details (Smoothly Shown When Selected) -->
    {#if isSelected}
      <div class="mt-3 pt-2.5 border-t border-[#B8DEEB]/80 text-xs text-[#718096] space-y-1.5">
        <div class="flex items-center justify-between">
          <span class="font-sans font-normal">Coords: <strong class="text-[#263747] font-mono font-normal tabular-nums">{formatCoords(plane.lat, plane.lon)}</strong></span>
          <span class="font-sans font-normal">Bearing: <strong class="text-[#168AAD] font-mono font-medium tabular-nums">BRG {plane.bearingDeg !== undefined ? `${Math.round(plane.bearingDeg)}°` : '--'}</strong></span>
        </div>

        <div class="flex items-center justify-between">
          <span class="font-sans font-normal">Squawk: <strong class="text-[#263747] font-mono font-normal tabular-nums">{plane.squawk || 'None'}</strong></span>
          <span class="font-sans font-normal">History: <strong class="text-[#263747] font-mono font-normal tabular-nums">{plane.trail?.length ?? 1} pts</strong></span>
          <span class="font-sans font-normal">Seen: <strong class="text-[#263747] font-mono font-normal tabular-nums">{plane.seen}s ago</strong></span>
        </div>

        {#if plane.route}
          <div class="text-xs text-[#718096] pt-1 border-t border-slate-100 flex items-center justify-between font-sans">
            <span class="font-normal">Route verification: <strong class="text-[#239B75] font-medium">{plane.route.check}</strong></span>
            <span class="text-[#718096]/70 font-mono text-xs">{plane.route.source}</span>
          </div>
        {/if}

        <div class="pt-1 flex justify-end">
          <span class="text-xs text-[#168AAD] hover:underline font-sans font-normal cursor-pointer">
            Click to deselect / collapse
          </span>
        </div>
      </div>
    {/if}
  </div>
</div>
