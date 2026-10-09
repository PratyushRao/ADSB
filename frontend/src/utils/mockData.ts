import type { Aircraft, ReceiverLocation } from '../types/aircraft';
import { calculateDistanceNm, calculateBearingDeg } from './geo';

export const DEFAULT_RECEIVER: ReceiverLocation = {
  name: 'Default Ground Station (VIDP / Delhi)',
  lat: 28.5562,
  lon: 77.1000,
  altitudeMeters: 237,
};

const SAMPLE_AIRCRAFT_CONFIGS = [
  { hex: '8008F1', callsign: 'AIC101', lat: 28.62, lon: 77.25, alt: 18500, speed: 410, heading: 240, vert: -1200 },
  { hex: '80054A', callsign: 'IGO5203', lat: 28.48, lon: 76.95, alt: 3200, speed: 175, heading: 95, vert: -700 },
  { hex: '800A3C', callsign: 'VTI819', lat: 28.75, lon: 77.05, alt: 24000, speed: 450, heading: 320, vert: 0 },
  { hex: '40051B', callsign: 'BAW143', lat: 28.35, lon: 77.30, alt: 36000, speed: 495, heading: 285, vert: 0 },
  { hex: '89642C', callsign: 'UAE510', lat: 28.20, lon: 76.80, alt: 38000, speed: 512, heading: 110, vert: 0 },
  { hex: '80029D', callsign: 'SEJ302', lat: 28.52, lon: 77.18, alt: 7400, speed: 230, heading: 280, vert: 1400 },
  { hex: '71038E', callsign: 'SIA403', lat: 28.80, lon: 77.40, alt: 31000, speed: 470, heading: 135, vert: -500 },
  { hex: '800911', callsign: 'AKJ1124', lat: 28.38, lon: 77.02, alt: 11200, speed: 290, heading: 45, vert: 800 },
];

/**
 * Generate or advance simulated aircraft around the receiver
 */
export function createInitialSimulation(receiver: ReceiverLocation): Aircraft[] {
  const now = Date.now();
  return SAMPLE_AIRCRAFT_CONFIGS.map((c) => {
    const dist = calculateDistanceNm(receiver.lat, receiver.lon, c.lat, c.lon);
    const bearing = calculateBearingDeg(receiver.lat, receiver.lon, c.lat, c.lon);
    return {
      id: c.hex,
      hex: c.hex,
      callsign: c.callsign,
      lat: c.lat,
      lon: c.lon,
      altitude: c.alt,
      speed: c.speed,
      heading: c.heading,
      verticalRate: c.vert,
      squawk: String(Math.floor(1000 + Math.random() * 6000)),
      seen: 0,
      lastUpdated: now,
      distanceNm: dist,
      bearingDeg: bearing,
      trail: [
        [c.lat - 0.015 * Math.cos((c.heading * Math.PI) / 180), c.lon - 0.015 * Math.sin((c.heading * Math.PI) / 180)],
        [c.lat, c.lon],
      ],
    };
  });
}

/**
 * Tick simulation step (moves planes along their heading and speed vector)
 */
export function advanceSimulation(aircraftList: Aircraft[], receiver: ReceiverLocation, dtSeconds: number = 1): Aircraft[] {
  const now = Date.now();
  return aircraftList.map((a) => {
    // 1 knot = 1 nautical mile per hour
    // dtSeconds hours = dtSeconds / 3600
    const distanceNmMoved = (a.speed * dtSeconds) / 3600;
    // 1 NM latitude ≈ 1 / 60 degrees ≈ 0.01666 degrees
    const headingRad = (a.heading * Math.PI) / 180;
    const dLat = (distanceNmMoved / 60) * Math.cos(headingRad);
    const dLon = ((distanceNmMoved / 60) * Math.sin(headingRad)) / Math.cos((a.lat * Math.PI) / 180);

    const newLat = a.lat + dLat;
    const newLon = a.lon + dLon;

    // Small heading drift or turn
    let newHeading = a.heading;
    if (Math.random() < 0.05) {
      newHeading = (a.heading + (Math.random() * 6 - 3) + 360) % 360;
    }

    // Altitude change based on vertical rate
    let newAlt = a.altitude;
    if (a.verticalRate) {
      newAlt = Math.max(0, Math.round(a.altitude + (a.verticalRate * dtSeconds) / 60));
    }

    const trail = [...a.trail];
    trail.push([newLat, newLon]);
    if (trail.length > 50) trail.shift();

    const dist = calculateDistanceNm(receiver.lat, receiver.lon, newLat, newLon);
    const bearing = calculateBearingDeg(receiver.lat, receiver.lon, newLat, newLon);

    return {
      ...a,
      lat: newLat,
      lon: newLon,
      altitude: newAlt,
      heading: newHeading,
      distanceNm: dist,
      bearingDeg: bearing,
      trail,
      lastUpdated: now,
      seen: 0,
    };
  });
}
