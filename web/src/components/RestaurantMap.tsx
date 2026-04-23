import { useMemo, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import type { Restaurant } from '../types';

// Fix Leaflet default marker icon issue with bundlers
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// @ts-expect-error - Leaflet icon default prototype fix
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

// Custom terracotta marker (matches new editorial palette)
const terracottaIcon = new L.Icon({
  iconUrl:
    'data:image/svg+xml;base64,' +
    btoa(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 32" width="24" height="32">
      <path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 20 12 20s12-12 12-20C24 5.4 18.6 0 12 0z" fill="#C94B1F"/>
      <circle cx="12" cy="11" r="4.5" fill="#FAF6F0"/>
    </svg>
  `),
  iconSize: [24, 32],
  iconAnchor: [12, 32],
  popupAnchor: [0, -32],
});

// Calgary bounding box
const CALGARY_BOUNDS = {
  south: 50.84,
  north: 51.21,
  west: -114.32,
  east: -113.86,
};

function isInCalgary(lat: number, lng: number) {
  return (
    lat >= CALGARY_BOUNDS.south &&
    lat <= CALGARY_BOUNDS.north &&
    lng >= CALGARY_BOUNDS.west &&
    lng <= CALGARY_BOUNDS.east
  );
}

function StarRating({ rating }: { rating: number }) {
  const stars = [];
  for (let i = 1; i <= 5; i++) {
    stars.push(
      <span
        key={i}
        className={i <= Math.round(rating) ? 'text-mustard' : 'text-border-warm'}
      >
        ★
      </span>
    );
  }
  return <span className="text-sm">{stars}</span>;
}

interface RestaurantMapProps {
  onOpenChat: (slug: string, name: string) => void;
  restaurants: Restaurant[];
}

export default function RestaurantMap({ onOpenChat, restaurants }: RestaurantMapProps) {
  const [map, setMap] = useState<L.Map | null>(null);
  const [userPos, setUserPos] = useState<[number, number] | null>(null);
  const [toast, setToast] = useState('');

  const geoRestaurants = useMemo(
    () => restaurants.filter((r) => r.lat !== null && r.lng !== null),
    [restaurants]
  );

  const loading = restaurants.length === 0;

  const handleLocate = useCallback(() => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        if (isInCalgary(latitude, longitude)) {
          map?.setView([latitude, longitude], 13);
          setUserPos([latitude, longitude]);
          setToast('');
        } else {
          setToast("Looks like you're not in Calgary. Map stays centered on the city.");
          setTimeout(() => setToast(''), 4000);
        }
      },
      () => {
        // Denied or error — do nothing
      }
    );
  }, [map]);

  return (
    <section id="map" className="pt-16 pb-4 md:pt-24 md:pb-6 px-4 border-t border-border-warm">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <p className="font-serif italic text-base md:text-lg text-sand mb-2 md:mb-3">
            know the menu before you go.
          </p>
          <h2 className="font-display text-3xl md:text-5xl font-medium text-ink tracking-tight">
            Tap a restaurant pin to dig into the menu.
          </h2>
        </div>

        <div className="relative overflow-hidden border border-border-warm bg-cream">
          {toast && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1001] bg-ink text-cream text-sm px-4 py-2 rounded-lg shadow-lg">
              {toast}
            </div>
          )}
          {!loading && (
            <button
              onClick={handleLocate}
              aria-label="Show my location"
              className="absolute bottom-10 right-4 z-[1000] w-10 h-10 rounded-full bg-terracotta text-cream flex items-center justify-center shadow-md hover:bg-terracotta-dark hover:scale-105 hover:shadow-lg transition-all"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="4" />
                <line x1="12" y1="2" x2="12" y2="6" />
                <line x1="12" y1="18" x2="12" y2="22" />
                <line x1="2" y1="12" x2="6" y2="12" />
                <line x1="18" y1="12" x2="22" y2="12" />
              </svg>
            </button>
          )}
          {loading ? (
            <div className="h-[500px] flex items-center justify-center">
              <div className="skeleton w-full h-full" />
            </div>
          ) : (
            <MapContainer
              center={[51.0447, -114.0719]}
              zoom={11}
              className="h-[500px] w-full"
              scrollWheelZoom={true}
              ref={setMap}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {userPos && (
                <CircleMarker
                  center={userPos}
                  radius={8}
                  pathOptions={{
                    color: '#3B82F6',
                    fillColor: '#3B82F6',
                    fillOpacity: 0.6,
                    weight: 2,
                  }}
                />
              )}
              <MarkerClusterGroup chunkedLoading>
                {geoRestaurants.map((restaurant) => (
                  <Marker
                    key={restaurant.slug}
                    position={[restaurant.lat!, restaurant.lng!]}
                    icon={terracottaIcon}
                  >
                    <Popup>
                      <div className="font-sans" style={{ minWidth: 240 }}>
                        {restaurant.photo_url && (
                          <img
                            src={restaurant.photo_url}
                            alt={restaurant.name}
                            style={{
                              width: '100%',
                              height: 140,
                              objectFit: 'cover',
                              borderTopLeftRadius: 12,
                              borderTopRightRadius: 12,
                              display: 'block',
                            }}
                            onError={(e) => {
                              (e.target as HTMLImageElement).style.display = 'none';
                            }}
                          />
                        )}
                        <div style={{ padding: 14 }}>
                          <h3 className="font-display font-semibold text-ink text-base mb-1">
                            {restaurant.name}
                          </h3>
                          {restaurant.rating ? (
                            <div className="flex items-center gap-1.5 mb-1">
                              <StarRating rating={restaurant.rating} />
                              <span className="text-xs text-sand">
                                ({restaurant.reviews} reviews)
                              </span>
                            </div>
                          ) : (
                            <p className="font-serif italic text-xs text-sand/70 mb-1">
                              No ratings yet
                            </p>
                          )}
                          {restaurant.address && (
                            <p className="text-xs text-sand mb-2">{restaurant.address}</p>
                          )}
                          <button
                            onClick={() => onOpenChat(restaurant.slug, restaurant.name)}
                            className="w-full text-center text-xs uppercase tracking-widest font-semibold text-terracotta hover:text-terracotta-dark transition-colors"
                          >
                            Chat about this menu →
                          </button>
                        </div>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </MarkerClusterGroup>
            </MapContainer>
          )}
        </div>
      </div>
    </section>
  );
}
