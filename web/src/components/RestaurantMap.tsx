import { useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
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
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="24" height="36">
      <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24C24 5.4 18.6 0 12 0z" fill="#C94B1F"/>
      <circle cx="12" cy="12" r="5" fill="#FAF6F0"/>
    </svg>
  `),
  iconSize: [24, 36],
  iconAnchor: [12, 36],
  popupAnchor: [0, -36],
});

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
  const geoRestaurants = useMemo(
    () => restaurants.filter((r) => r.lat !== null && r.lng !== null),
    [restaurants]
  );

  const loading = restaurants.length === 0;

  return (
    <section id="map" className="pt-16 pb-4 md:pt-24 md:pb-6 px-4 border-t border-border-warm">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h2 className="font-display text-3xl md:text-5xl font-medium text-ink tracking-tight">
            {restaurants.length || 487} restaurants. One map. Tap a pin to explore the menu.
          </h2>
        </div>

        <div className="overflow-hidden border border-border-warm bg-cream">
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
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
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
                        {restaurant.rating && (
                          <div className="flex items-center gap-1.5 mb-1">
                            <StarRating rating={restaurant.rating} />
                            <span className="text-xs text-sand">
                              ({restaurant.reviews ?? 0})
                            </span>
                          </div>
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
            </MapContainer>
          )}
        </div>
      </div>
    </section>
  );
}
