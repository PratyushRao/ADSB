import type { Aircraft, ReceiverLocation } from '../types/aircraft';
import { calculateDistanceNm, calculateBearingDeg } from './geo';

/**
 * Universal ADS-B JSON parser capable of decoding:
 * 1. dump1090 / readsb / tar1090 aircraft.json format
 * 2. OpenSky Network states JSON
 * 3. Array of custom aircraft objects
 * 4. Nested { data: [...] } or { flights: [...] } structures
 * 5. Single aircraft JSON object
 */
export function parseAdsbPayload(
  raw: any,
  existingAircraftMap: Map<string, Aircraft>,
  receiver?: ReceiverLocation
): Aircraft[] {
  if (!raw) return Array.from(existingAircraftMap.values());

  let rawList: any[] = [];

  // Determine container structure
  if (Array.isArray(raw)) {
    rawList = raw;
  } else if (raw.aircraft && Array.isArray(raw.aircraft)) {
    rawList = raw.aircraft; // dump1090 / readsb
  } else if (raw.flights && Array.isArray(raw.flights)) {
    rawList = raw.flights;
  } else if (raw.data && Array.isArray(raw.data)) {
    rawList = raw.data;
  } else if (raw.states && Array.isArray(raw.states)) {
    // OpenSky Network format: array of tuples
    return parseOpenSkyStates(raw.states, existingAircraftMap, receiver);
  } else if (typeof raw === 'object' && (raw.lat !== undefined || raw.latitude !== undefined)) {
    rawList = [raw];
  } else {
    // Check if values inside object are aircraft
    const values = Object.values(raw);
    if (values.length > 0 && typeof values[0] === 'object') {
      rawList = values;
    }
  }

  const now = Date.now();
  const updatedMap = new Map(existingAircraftMap);

  for (const item of rawList) {
    if (!item || typeof item !== 'object') continue;

    // Resolve lat / lon
    const lat = item.lat ?? item.latitude ?? item.latitude_deg ?? item.pos?.[0];
    const lon = item.lon ?? item.lng ?? item.longitude ?? item.longitude_deg ?? item.pos?.[1];

    // Must have valid coordinates to render on map
    if (typeof lat !== 'number' || typeof lon !== 'number' || isNaN(lat) || isNaN(lon)) {
      continue;
    }

    // Resolve identifier
    const hex = String(item.hex ?? item.icao ?? item.icao24 ?? item.id ?? item.callsign ?? `${lat.toFixed(3)}_${lon.toFixed(3)}`)
      .trim()
      .toUpperCase();

    // Resolve callsign / flight number
    let callsign = String(item.flight ?? item.callsign ?? item.ident ?? hex).trim();
    if (!callsign || callsign === 'null') callsign = hex;

    // Resolve altitude
    const altitude = Number(
      item.altitude ?? item.alt_baro ?? item.alt_geom ?? item.alt ?? item.baro_altitude ?? 0
    );

    // Resolve speed (knots)
    const speed = Number(item.speed ?? item.gs ?? item.velocity ?? item.ground_speed ?? 0);

    // Resolve heading / track (degrees)
    const heading = Number(
      item.heading ?? item.track ?? item.true_track ?? item.course ?? item.bearing ?? 0
    );

    // Resolve vertical rate
    const verticalRate =
      item.vert_rate !== undefined || item.vertical_rate !== undefined || item.climb !== undefined
        ? Number(item.vert_rate ?? item.vertical_rate ?? item.climb)
        : undefined;

    const squawk = item.squawk ? String(item.squawk).trim() : undefined;
    const category = item.category ? String(item.category) : undefined;
    const seen = Number(item.seen ?? 0);

    // Calculate distance and bearing if receiver location exists
    let distanceNm: number | undefined;
    let bearingDeg: number | undefined;
    if (receiver) {
      distanceNm = calculateDistanceNm(receiver.lat, receiver.lon, lat, lon);
      bearingDeg = calculateBearingDeg(receiver.lat, receiver.lon, lat, lon);
    }

    // Build or update history trail
    const existing = updatedMap.get(hex);
    let trail: [number, number][] = existing?.trail ? [...existing.trail] : [];
    
    // Only push point if plane has moved sufficiently (> ~50m) to keep memory lean
    if (
      trail.length === 0 ||
      Math.abs(trail[trail.length - 1][0] - lat) > 0.0005 ||
      Math.abs(trail[trail.length - 1][1] - lon) > 0.0005
    ) {
      trail.push([lat, lon]);
      if (trail.length > 50) {
        trail.shift(); // retain last 50 points
      }
    }

    const aircraft: Aircraft = {
      id: hex,
      hex,
      callsign,
      lat,
      lon,
      altitude: isNaN(altitude) ? 0 : altitude,
      speed: isNaN(speed) ? 0 : speed,
      heading: isNaN(heading) ? 0 : (heading + 360) % 360,
      verticalRate,
      squawk,
      category,
      seen,
      lastUpdated: now,
      distanceNm,
      bearingDeg,
      trail,
      route: item.route && typeof item.route === 'object' ? item.route : undefined,
    };

    updatedMap.set(hex, aircraft);
  }

  return Array.from(updatedMap.values());
}

/**
 * Handle OpenSky Network array of states
 */
function parseOpenSkyStates(
  states: any[][],
  existingAircraftMap: Map<string, Aircraft>,
  receiver?: ReceiverLocation
): Aircraft[] {
  const now = Date.now();
  const updatedMap = new Map(existingAircraftMap);

  for (const st of states) {
    if (!Array.isArray(st)) continue;
    const hex = String(st[0] ?? '').toUpperCase();
    const callsign = String(st[1] ?? hex).trim();
    const lon = Number(st[5]);
    const lat = Number(st[6]);
    const altitudeMeters = Number(st[7] ?? 0);
    const altitude = Math.round(altitudeMeters * 3.28084); // meters to feet
    const speedMs = Number(st[9] ?? 0);
    const speed = Math.round(speedMs * 1.94384); // m/s to knots
    const heading = Number(st[10] ?? 0);
    const vertRateMs = Number(st[11] ?? 0);
    const verticalRate = Math.round(vertRateMs * 196.85);

    if (isNaN(lat) || isNaN(lon) || !hex) continue;

    let distanceNm: number | undefined;
    let bearingDeg: number | undefined;
    if (receiver) {
      distanceNm = calculateDistanceNm(receiver.lat, receiver.lon, lat, lon);
      bearingDeg = calculateBearingDeg(receiver.lat, receiver.lon, lat, lon);
    }

    const existing = updatedMap.get(hex);
    let trail: [number, number][] = existing?.trail ? [...existing.trail] : [];
    if (
      trail.length === 0 ||
      Math.abs(trail[trail.length - 1][0] - lat) > 0.0005 ||
      Math.abs(trail[trail.length - 1][1] - lon) > 0.0005
    ) {
      trail.push([lat, lon]);
      if (trail.length > 50) trail.shift();
    }

    updatedMap.set(hex, {
      id: hex,
      hex,
      callsign: callsign || hex,
      lat,
      lon,
      altitude,
      speed,
      heading: (heading + 360) % 360,
      verticalRate,
      seen: 0,
      lastUpdated: now,
      distanceNm,
      bearingDeg,
      trail,
    });
  }

  return Array.from(updatedMap.values());
}
