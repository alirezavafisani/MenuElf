// Small helpers for the Google Maps handoff and distance display.
// MenuElf owns the dish. Everything about the restaurant itself (directions,
// hours, photos, reviews) is Google's job, so we deep-link out instead of
// rebuilding a worse version of Google Maps here.

export interface RestaurantGeo {
  lat: number | null;
  lng: number | null;
  address: string | null;
}

export interface UserLocation {
  lat: number;
  lng: number;
}

/** Free Google Maps deep link. Name plus address gives Google enough to land
 *  on the right listing, with hours, reviews, photos and directions. */
export function googleMapsUrl(name: string, address?: string | null): string {
  const query = address ? `${name}, ${address}` : `${name}, Calgary, AB`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

/** Haversine distance in km between two points. */
export function distanceKm(a: UserLocation, b: { lat: number; lng: number }): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function formatDistance(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${km.toFixed(1)} km`;
}
