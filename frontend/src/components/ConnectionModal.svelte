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
    onUpdateEndpoint(endpointInput, Math.max(1, intervalSec) * 1000);
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
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
    <div class="w-full max-w-xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <span class="text-xl">📡</span>
          <h2 class="text-lg font-bold text-white tracking-wide">ADS-B Data Source Settings</h2>
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

      <!-- Navigation Tabs -->
      <div class="flex border-b border-slate-800 bg-slate-950/40 px-6 pt-2">
        <button
          onclick={() => (activeTab = 'backend')}
          class="px-4 py-2 text-sm font-medium border-b-2 transition {activeTab === 'backend' ? 'border-cyan-400 text-cyan-300' : 'border-transparent text-slate-400 hover:text-slate-200'}"
        >
          Live Backend Endpoint
        </button>
        <button
          onclick={() => (activeTab = 'upload')}
          class="px-4 py-2 text-sm font-medium border-b-2 transition {activeTab === 'upload' ? 'border-cyan-400 text-cyan-300' : 'border-transparent text-slate-400 hover:text-slate-200'}"
        >
          JSON File / Paste
        </button>
        <button
          onclick={() => (activeTab = 'receiver')}
          class="px-4 py-2 text-sm font-medium border-b-2 transition {activeTab === 'receiver' ? 'border-cyan-400 text-cyan-300' : 'border-transparent text-slate-400 hover:text-slate-200'}"
        >
          Receiver Coordinates
        </button>
      </div>

      <!-- Body -->
      <div class="p-6 overflow-y-auto space-y-4">
        {#if activeTab === 'backend'}
          <div class="space-y-4">
            <div>
              <label for="endpoint-url" class="block text-xs font-mono font-medium text-slate-300 mb-1.5 uppercase">
                Backend Endpoint URL (HTTP GET or WebSocket ws://)
              </label>
              <input
                id="endpoint-url"
                type="text"
                bind:value={endpointInput}
                placeholder="http://localhost:8080/data.json or ws://localhost:8080/ws"
                class="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 font-mono text-sm text-cyan-300 focus:outline-none focus:border-cyan-500"
              />
              <p class="mt-1.5 text-xs text-slate-400">
                Point this to your ADS-B demodulator / DSP backend outputting JSON (supports HTTP GET polling or live WebSocket stream).
              </p>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="poll-rate" class="block text-xs font-mono font-medium text-slate-300 mb-1.5 uppercase">
                  Poll Rate (seconds)
                </label>
                <input
                  id="poll-rate"
                  type="number"
                  min="0.5"
                  step="0.5"
                  bind:value={intervalSec}
                  class="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-700 font-mono text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <span class="block text-xs font-mono font-medium text-slate-300 mb-1.5 uppercase">
                  Simulation Mode
                </span>
                <button
                  type="button"
                  onclick={() => onToggleSimulation(feedStatus.mode !== 'simulation')}
                  class="w-full py-2 px-3 rounded-xl font-mono text-sm border transition {feedStatus.mode === 'simulation' ? 'bg-cyan-950/80 border-cyan-500 text-cyan-300' : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'}"
                >
                  {feedStatus.mode === 'simulation' ? 'Active (Demo Flights)' : 'Disabled'}
                </button>
              </div>
            </div>

            <div class="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs font-mono space-y-1">
              <div class="text-slate-400">Supported formats:</div>
              <ul class="list-disc list-inside text-slate-300 space-y-0.5">
                <li><code>dump1090 / readsb</code> ({"{"} aircraft: [...] {"}"})</li>
                <li>Custom JSON array ([{"{"} callsign, lat, lon, heading, altitude {"}"}])</li>
                <li>OpenSky Network JSON ({"{"} states: [...] {"}"})</li>
              </ul>
            </div>

            <div class="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onclick={onClose}
                class="px-4 py-2 rounded-xl text-sm font-medium text-slate-300 hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={handleSaveBackend}
                class="px-5 py-2 rounded-xl text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20 transition"
              >
                Connect & Poll
              </button>
            </div>
          </div>
        {:else if activeTab === 'upload'}
          <div class="space-y-4">
            <div>
              <label for="json-file-input" class="block text-xs font-mono font-medium text-slate-300 mb-1.5 uppercase">
                Upload JSON File
              </label>
              <input
                id="json-file-input"
                type="file"
                accept=".json,application/json"
                onchange={handleFileUpload}
                class="block w-full text-sm text-slate-400 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-cyan-500 file:text-slate-950 hover:file:bg-cyan-400 cursor-pointer"
              />
            </div>

            <div class="relative flex py-1 items-center">
              <div class="flex-grow border-t border-slate-800"></div>
              <span class="flex-shrink mx-4 text-xs font-mono text-slate-500 uppercase">Or Paste Raw JSON</span>
              <div class="flex-grow border-t border-slate-800"></div>
            </div>

            <div>
              <textarea
                rows="6"
                bind:value={pastedJson}
                placeholder={`{\n  "aircraft": [\n    {\n      "hex": "8008F1",\n      "flight": "AIC101",\n      "lat": 28.62,\n      "lon": 77.25,\n      "altitude": 18500,\n      "track": 240,\n      "speed": 410\n    }\n  ]\n}`}
                class="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 font-mono text-xs text-cyan-300 focus:outline-none focus:border-cyan-500 resize-none"
              ></textarea>
            </div>

            <div class="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onclick={onClose}
                class="px-4 py-2 rounded-xl text-sm font-medium text-slate-300 hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={handleApplyPastedJson}
                disabled={!pastedJson.trim()}
                class="px-5 py-2 rounded-xl text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 shadow-lg transition"
              >
                Load Pasted JSON
              </button>
            </div>
          </div>
        {:else if activeTab === 'receiver'}
          <div class="space-y-4">
            <div>
              <label for="rx-name" class="block text-xs font-mono font-medium text-slate-300 mb-1.5 uppercase">Station Name</label>
              <input
                id="rx-name"
                type="text"
                bind:value={rxName}
                class="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-700 font-mono text-sm text-white focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="rx-lat" class="block text-xs font-mono font-medium text-slate-300 mb-1.5 uppercase">Latitude (°)</label>
                <input
                  id="rx-lat"
                  type="number"
                  step="0.0001"
                  bind:value={rxLat}
                  class="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-700 font-mono text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label for="rx-lon" class="block text-xs font-mono font-medium text-slate-300 mb-1.5 uppercase">Longitude (°)</label>
                <input
                  id="rx-lon"
                  type="number"
                  step="0.0001"
                  bind:value={rxLon}
                  class="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-700 font-mono text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <p class="text-xs text-slate-400">
              Configuring your antenna location allows accurate distance (NM) and radial bearing calculations from your receiver to tracked aircraft.
            </p>

            <div class="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onclick={onClose}
                class="px-4 py-2 rounded-xl text-sm font-medium text-slate-300 hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={handleSaveReceiver}
                class="px-5 py-2 rounded-xl text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-lg transition"
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
