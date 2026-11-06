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
  route?: FlightRoute; // origin/destination looked up from the callsign (backend)
}

export interface RouteAirport {
  iata?: string | null;
  icao?: string | null;
  name?: string | null;
  city?: string | null;
  country?: string | null;
  lat?: number | null;
  lon?: number | null;
}

export interface FlightRoute {
  flight: string; // IATA flight number, e.g. 6E5203 (callsign IGO5203)
  airline?: string | null;
  origin: RouteAirport;
  destination: RouteAirport;
  source: string; // route database used
  // Route cross-checked against the live decoded position/track
  check: 'plausible' | 'off-route' | 'reverse' | 'unverified';
  checkDetail: string;
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
