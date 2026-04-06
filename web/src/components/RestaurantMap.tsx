import { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { getRestaurants } from '../api';
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

// Custom orange marker
const orangeIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="24" height="36">
      <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24C24 5.4 18.6 0 12 0z" fill="#E85D3A"/>
      <circle cx="12" cy="12" r="5" fill="white"/>
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
      <span key={i} className={i <= Math.round(rating) ? 'text-amber-400' : 'text-stone-300'}>
        ★
      </span>
    );
  }
  return <span className="text-sm">{stars}</span>;
}

interface RestaurantMapProps {
  onOpenChat: (slug: string, name: string) => void;
}

export default function RestaurantMap({ onOpenChat }: RestaurantMapProps) {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRestaurants()
      .then((data) => setRestaurants(data.restaurants))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const geoRestaurants = useMemo(
    () => restaurants.filter((r) => r.lat !== null && r.lng !== null),
    [restaurants]
  );

  return (
    <section id="map" className="py-16 px-4">
      <div className="max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold text-stone-900 mb-2 text-center">
          Explore {restaurants.length || 487} Calgary Restaurants
        </h2>
        <p className="text-stone-500 text-center mb-8">
          Hover over any pin to learn more and chat about the menu
        </p>

        <div className="rounded-2xl overflow-hidden border border-stone-200 shadow-sm bg-white">
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
                  icon={orangeIcon}
                  eventHandlers={{
                    mouseover: (e) => { e.target.openPopup(); },
                    mouseout: (e) => { e.target.closePopup(); },
                  }}
                >
                  <Popup>
                    <div className="p-3 min-w-[200px]">
                      <h3 className="font-semibold text-stone-900 text-sm mb-1">
                        {restaurant.name}
                      </h3>
                      {restaurant.rating && (
                        <div className="flex items-center gap-1.5 mb-1">
                          <StarRating rating={restaurant.rating} />
                          <span className="text-xs text-stone-500">
                            ({restaurant.reviews ?? 0})
                          </span>
                        </div>
                      )}
                      {restaurant.address && (
                        <p className="text-xs text-stone-500 mb-2">{restaurant.address}</p>
                      )}
                      <button
                        onClick={() => onOpenChat(restaurant.slug, restaurant.name)}
                        className="w-full text-center text-xs font-semibold text-accent hover:text-accent-hover transition-colors"
                      >
                        Chat about this menu →
                      </button>
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
