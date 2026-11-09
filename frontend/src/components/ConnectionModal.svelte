<script lang="ts">
  import type { FeedStatus, ReceiverLocation } from '../types/aircraft';

  interface Props {
    isOpen: boolean;
    feedStatus: FeedStatus;
    receiver: ReceiverLocation;
    onClose: () => void;
    onUpdateEndpoint: (url: string, intervalMs: number) => void;
    onLoadJsonContent: (jsonText: string) => void;
    onUpdateReceiver: (receiver: ReceiverLocation) => void;
    onToggleSimulation: (enable: boolean) => void;
  }

  let {
    isOpen,
    feedStatus,
    receiver,
    onClose,
    onUpdateEndpoint,
    onLoadJsonContent,
    onUpdateReceiver,
    onToggleSimulation,
  }: Props = $props();

  let activeTab = $state<'backend' | 'upload' | 'receiver'>('backend');

  // Local form state
  let endpointInput = $state('');
  let intervalSec = $state(2);
  let pastedJson = $state('');
  let rxName = $state('');
  let rxLat = $state(0);
  let rxLon = $state(0);

  $effect(() => {
    endpointInput = feedStatus.endpointUrl;
    intervalSec = feedStatus.pollingIntervalMs / 1000;
  });

  $effect(() => {
    rxName = receiver.name;
    rxLat = receiver.lat;
    rxLon = receiver.lon;
  });

  function handleSaveBackend() {
    onUpdateEndpoint(endpointInput, Math.max(0.5, intervalSec) * 1000);
    onClose();
  }

  function handleSaveReceiver() {
    onUpdateReceiver({
      name: rxName,
      lat: Number(rxLat),
      lon: Number(rxLon),
      altitudeMeters: receiver.altitudeMeters,
    });
    onClose();
  }

  function applyPreset(name: string, lat: number, lon: number) {
    rxName = name;
    rxLat = lat;
    rxLon = lon;
  }

  function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (text) {
        onLoadJsonContent(text);
        onClose();
      }
    };
    reader.readAsText(file);
  }

  function handleApplyPastedJson() {
    if (pastedJson.trim()) {
      onLoadJsonContent(pastedJson);
      onClose();
    }
  }

  function loadSampleJson() {
    pastedJson = JSON.stringify(
      {
        aircraft: [
          {
            hex: "8008F1",
            flight: "AIC101",
            lat: 28.62,
            lon: 77.25,
            alt_baro: 18500,
            track: 240,
            gs: 410,
            vert_rate: -1200,
            squawk: "3412"
          },
          {
            hex: "80054A",
            flight: "IGO5203",
            lat: 28.48,
            lon: 76.95,
            alt_baro: 3200,
            track: 95,
            gs: 175,
            vert_rate: -700,
            squawk: "2104"
          }
        ]
      },
      null,
      2
    );
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#263747]/40 backdrop-blur-xs select-none">
    <div class="w-full max-w-xl bg-white border border-[#E3EAF0] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 bg-[#F4F7FA] border-b border-[#E3EAF0] flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-white border border-[#E3EAF0] text-[#168AAD] flex items-center justify-center shadow-2xs">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" stroke-width="1.8" />
              <circle cx="12" cy="12" r="3" fill="currentColor" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 3v3m0 12v3M3 12h3m12 0h3" />
            </svg>
          </div>
          <div>
            <h2 class="text-base font-bold text-[#263747]">Data Source & Receiver Settings</h2>
            <p class="text-xs text-[#718096]">Configure ADS-B demodulator ingestion and ground station antenna</p>
          </div>
        </div>
        <button
          onclick={onClose}
          class="text-[#718096] hover:text-[#263747] p-1.5 rounded-lg hover:bg-slate-200/60 transition"
          aria-label="Close"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Navigation Tabs -->
      <div class="flex border-b border-[#E3EAF0] bg-[#F8FAFC] px-6">
        <button
          onclick={() => (activeTab = 'backend')}
          class="px-4 py-3 text-xs font-semibold border-b-2 transition flex items-center gap-2 {activeTab === 'backend' ? 'border-[#168AAD] text-[#168AAD]' : 'border-transparent text-[#718096] hover:text-[#263747]'}"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Live Backend Feed
        </button>
        <button
          onclick={() => (activeTab = 'upload')}
          class="px-4 py-3 text-xs font-semibold border-b-2 transition flex items-center gap-2 {activeTab === 'upload' ? 'border-[#168AAD] text-[#168AAD]' : 'border-transparent text-[#718096] hover:text-[#263747]'}"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          JSON File / Paste
        </button>
        <button
          onclick={() => (activeTab = 'receiver')}
          class="px-4 py-3 text-xs font-semibold border-b-2 transition flex items-center gap-2 {activeTab === 'receiver' ? 'border-[#168AAD] text-[#168AAD]' : 'border-transparent text-[#718096] hover:text-[#263747]'}"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Receiver Coordinates
        </button>
      </div>

      <!-- Body -->
      <div class="p-6 overflow-y-auto space-y-4">
        {#if activeTab === 'backend'}
          <div class="space-y-4">
            <div>
              <label for="endpoint-url" class="block text-xs font-semibold text-[#263747] mb-1.5 uppercase font-mono">
                Demodulator / Backend Endpoint URL
              </label>
              <div class="relative">
                <input
                  id="endpoint-url"
                  type="text"
                  bind:value={endpointInput}
                  placeholder="ws://127.0.0.1:8000/ws or http://127.0.0.1:8000/api/aircraft"
                  class="w-full px-3.5 py-2.5 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] font-mono text-xs text-[#263747] focus:outline-none focus:border-[#168AAD] focus:bg-white focus:ring-1 focus:ring-[#168AAD]/30"
                />
              </div>
              <p class="mt-1.5 text-xs text-[#718096]">
                Supports real-time WebSocket streams (<code class="text-[#168AAD]">ws://</code>, <code class="text-[#168AAD]">wss://</code>) or periodic HTTP GET polling.
              </p>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="poll-rate" class="block text-xs font-semibold text-[#263747] mb-1.5 uppercase font-mono">
                  Poll Rate (seconds)
                </label>
                <input
                  id="poll-rate"
                  type="number"
                  min="0.5"
                  step="0.5"
                  bind:value={intervalSec}
                  class="w-full px-3.5 py-2 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] font-mono text-xs text-[#263747] focus:outline-none focus:border-[#168AAD] focus:bg-white"
                />
              </div>

              <div>
                <span class="block text-xs font-semibold text-[#263747] mb-1.5 uppercase font-mono">
                  Simulation Demo Traffic
                </span>
                <button
                  type="button"
                  onclick={() => onToggleSimulation(feedStatus.mode !== 'simulation')}
                  class="w-full py-2 px-3 rounded-xl font-mono text-xs border transition flex items-center justify-center gap-2
                    {feedStatus.mode === 'simulation'
                      ? 'bg-[#EBF5F8] border-[#168AAD] text-[#168AAD] font-bold shadow-2xs'
                      : 'bg-[#F8FAFC] border-[#E3EAF0] text-[#718096] hover:bg-slate-100'}"
                >
                  <span class="w-2 h-2 rounded-full {feedStatus.mode === 'simulation' ? 'bg-[#168AAD] animate-ping' : 'bg-slate-300'}"></span>
                  {feedStatus.mode === 'simulation' ? 'Active (Demo Flights)' : 'Enable Simulation'}
                </button>
              </div>
            </div>

            <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] text-xs space-y-1.5">
              <div class="font-semibold text-[#263747] flex items-center gap-1.5">
                <span class="text-[#168AAD]">ℹ</span> Supported ADS-B Message Schemas:
              </div>
              <div class="flex flex-wrap gap-1.5 pt-1">
                <span class="px-2 py-0.5 rounded bg-white border border-[#E3EAF0] font-mono text-[10px] text-[#263747]">dump1090 / readsb / tar1090</span>
                <span class="px-2 py-0.5 rounded bg-white border border-[#E3EAF0] font-mono text-[10px] text-[#263747]">OpenSky Network (states array)</span>
                <span class="px-2 py-0.5 rounded bg-white border border-[#E3EAF0] font-mono text-[10px] text-[#263747]">Custom Aircraft JSON Array</span>
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-2 border-t border-[#E3EAF0]">
              <button
                type="button"
                onclick={onClose}
                class="px-4 py-2 rounded-xl text-xs font-semibold text-[#718096] hover:text-[#263747] hover:bg-[#F4F7FA] transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={handleSaveBackend}
                class="px-5 py-2 rounded-xl text-xs font-semibold bg-[#168AAD] hover:bg-[#13708D] text-white shadow-sm transition"
              >
                Connect & Poll
              </button>
            </div>
          </div>
        {:else if activeTab === 'upload'}
          <div class="space-y-4">
            <div>
              <label for="json-file-input" class="block text-xs font-semibold text-[#263747] mb-1.5 uppercase font-mono">
                Upload JSON File
              </label>
              <input
                id="json-file-input"
                type="file"
                accept=".json,application/json"
                onchange={handleFileUpload}
                class="block w-full text-xs text-[#718096] file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[#168AAD] file:text-white hover:file:bg-[#13708D] cursor-pointer bg-[#F8FAFC] border border-[#E3EAF0] rounded-xl p-1.5"
              />
            </div>

            <div class="relative flex py-1 items-center">
              <div class="flex-grow border-t border-[#E3EAF0]"></div>
              <span class="flex-shrink mx-4 text-[10px] font-mono text-[#718096] uppercase font-bold">Or Paste Raw ADS-B JSON</span>
              <div class="flex-grow border-t border-[#E3EAF0]"></div>
            </div>

            <div>
              <div class="flex justify-between items-center mb-1">
                <span class="text-xs text-[#718096]">Enter JSON payload:</span>
                <button
                  type="button"
                  onclick={loadSampleJson}
                  class="text-[11px] font-mono text-[#168AAD] hover:underline"
                >
                  Insert Sample Payload
                </button>
              </div>
              <textarea
                rows="6"
                bind:value={pastedJson}
                placeholder={`{\n  "aircraft": [\n    {\n      "hex": "8008F1",\n      "flight": "AIC101",\n      "lat": 28.62,\n      "lon": 77.25,\n      "altitude": 18500,\n      "track": 240,\n      "speed": 410\n    }\n  ]\n}`}
                class="w-full p-3 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] font-mono text-xs text-[#263747] focus:outline-none focus:border-[#168AAD] focus:bg-white resize-none"
              ></textarea>
            </div>

            <div class="flex justify-end gap-3 pt-2 border-t border-[#E3EAF0]">
              <button
                type="button"
                onclick={onClose}
                class="px-4 py-2 rounded-xl text-xs font-semibold text-[#718096] hover:text-[#263747] hover:bg-[#F4F7FA] transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={handleApplyPastedJson}
                disabled={!pastedJson.trim()}
                class="px-5 py-2 rounded-xl text-xs font-semibold bg-[#168AAD] hover:bg-[#13708D] disabled:opacity-50 text-white shadow-sm transition"
              >
                Load Pasted JSON
              </button>
            </div>
          </div>
        {:else if activeTab === 'receiver'}
          <div class="space-y-4">
            <div>
              <label for="rx-name" class="block text-xs font-semibold text-[#263747] mb-1.5 uppercase font-mono">
                Ground Station / Receiver Name
              </label>
              <input
                id="rx-name"
                type="text"
                bind:value={rxName}
                class="w-full px-3.5 py-2 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] font-mono text-xs text-[#263747] focus:outline-none focus:border-[#168AAD] focus:bg-white"
              />
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="rx-lat" class="block text-xs font-semibold text-[#263747] mb-1.5 uppercase font-mono">
                  Antenna Latitude (°)
                </label>
                <input
                  id="rx-lat"
                  type="number"
                  step="0.0001"
                  bind:value={rxLat}
                  class="w-full px-3.5 py-2 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] font-mono text-xs text-[#263747] focus:outline-none focus:border-[#168AAD] focus:bg-white"
                />
              </div>

              <div>
                <label for="rx-lon" class="block text-xs font-semibold text-[#263747] mb-1.5 uppercase font-mono">
                  Antenna Longitude (°)
                </label>
                <input
                  id="rx-lon"
                  type="number"
                  step="0.0001"
                  bind:value={rxLon}
                  class="w-full px-3.5 py-2 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0] font-mono text-xs text-[#263747] focus:outline-none focus:border-[#168AAD] focus:bg-white"
                />
              </div>
            </div>

            <!-- Quick Geographic Presets -->
            <div class="p-3 rounded-xl bg-[#F8FAFC] border border-[#E3EAF0]">
              <span class="block text-[10px] font-mono uppercase text-[#718096] font-semibold mb-2">
                Quick Location Presets:
              </span>
              <div class="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onclick={() => applyPreset('Delhi Station (VIDP)', 28.5562, 77.1000)}
                  class="px-2 py-1 rounded bg-white hover:bg-[#EBF5F8] border border-[#E3EAF0] text-[11px] text-[#263747] font-medium transition"
                >
                  Delhi (VIDP)
                </button>
                <button
                  type="button"
                  onclick={() => applyPreset('London Heathrow (EGLL)', 51.4700, -0.4543)}
                  class="px-2 py-1 rounded bg-white hover:bg-[#EBF5F8] border border-[#E3EAF0] text-[11px] text-[#263747] font-medium transition"
                >
                  London (EGLL)
                </button>
                <button
                  type="button"
                  onclick={() => applyPreset('New York JFK (KJFK)', 40.6413, -73.7781)}
                  class="px-2 py-1 rounded bg-white hover:bg-[#EBF5F8] border border-[#E3EAF0] text-[11px] text-[#263747] font-medium transition"
                >
                  New York (KJFK)
                </button>
                <button
                  type="button"
                  onclick={() => applyPreset('Frankfurt (EDDF)', 50.0379, 8.5622)}
                  class="px-2 py-1 rounded bg-white hover:bg-[#EBF5F8] border border-[#E3EAF0] text-[11px] text-[#263747] font-medium transition"
                >
                  Frankfurt (EDDF)
                </button>
                <button
                  type="button"
                  onclick={() => applyPreset('Tokyo Haneda (RJTT)', 35.5494, 139.7798)}
                  class="px-2 py-1 rounded bg-white hover:bg-[#EBF5F8] border border-[#E3EAF0] text-[11px] text-[#263747] font-medium transition"
                >
                  Tokyo (RJTT)
                </button>
              </div>
            </div>

            <p class="text-xs text-[#718096] leading-relaxed">
              Antenna coordinates define the geographic origin for 10-100 NM radar range rings and calculate exact aircraft distance (NM) and radial bearing.
            </p>

            <div class="flex justify-end gap-3 pt-2 border-t border-[#E3EAF0]">
              <button
                type="button"
                onclick={onClose}
                class="px-4 py-2 rounded-xl text-xs font-semibold text-[#718096] hover:text-[#263747] hover:bg-[#F4F7FA] transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={handleSaveReceiver}
                class="px-5 py-2 rounded-xl text-xs font-semibold bg-[#168AAD] hover:bg-[#13708D] text-white shadow-sm transition"
              >
                Update Receiver
              </button>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
