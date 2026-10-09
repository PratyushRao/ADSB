export interface Aircraft {
  id: string; // Hex ICAO code or unique identifier
  hex: string;
  callsign: string;
  lat: number;
  lon: number;
  altitude: number; // in feet
  speed: number; // in knots (ground speed)
  heading: number; // in degrees (0-360)
  verticalRate?: number; // ft/min
  squawk?: string;
  category?: string;
  seen: number; // seconds ago
  lastUpdated: number; // timestamp
  distanceNm?: number; // distance from receiver in nautical miles
  bearingDeg?: number; // bearing from receiver
  trail: [number, number][]; // [lat, lon] history for flight path
}

export interface ReceiverLocation {
  lat: number;
  lon: number;
  altitudeMeters: number;
  name: string;
}

export type ConnectionMode = 'poll' | 'websocket' | 'file' | 'simulation';

export interface FeedStatus {
  mode: ConnectionMode;
  connected: boolean;
  endpointUrl: string;
  pollingIntervalMs: number;
  lastFetchTime: number | null;
  lastMessageCount: number;
  totalMessagesReceived: number;
  error: string | null;
}
