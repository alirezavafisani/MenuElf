import { useState, useCallback, useEffect, useMemo } from 'react';
import { getRestaurants } from './api';
import type { Restaurant } from './types';
import type { RestaurantGeo, UserLocation } from './geo';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import DiscoveryModes from './components/DiscoveryModes';
import DishSearch from './components/DishSearch';
import ChatPanel from './components/ChatPanel';
import Footer from './components/Footer';

export default function App() {
  const [chatRestaurant, setChatRestaurant] = useState<{
    slug: string;
    name: string;
  } | null>(null);

  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [userLoc, setUserLoc] = useState<UserLocation | null>(null);
  const [locDenied, setLocDenied] = useState(false);

  useEffect(() => {
    getRestaurants()
      .then((data) => setRestaurants(data.restaurants))
      .catch(() => {});
  }, []);

  const restaurantPhotoMap = useMemo(() => {
    const map: Record<string, string> = {};
    restaurants.forEach((r) => {
      if (r.photo_url) map[r.slug] = r.photo_url;
    });
    return map;
  }, [restaurants]);

  // Everything the dish cards need to hand the restaurant off to Google Maps
  // and show how far away it is. The restaurant itself is Google's territory.
  const restaurantGeoMap = useMemo(() => {
    const map: Record<string, RestaurantGeo> = {};
    restaurants.forEach((r) => {
      map[r.slug] = { lat: r.lat, lng: r.lng, address: r.address };
    });
    return map;
  }, [restaurants]);

  const requestLocation = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setLocDenied(true);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLoc({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocDenied(false);
      },
      () => setLocDenied(true),
      { maximumAge: 300000, timeout: 8000 }
    );
  }, []);

  const openChat = useCallback((slug: string, name: string) => {
    setChatRestaurant({ slug, name });
  }, []);

  const closeChat = useCallback(() => {
    setChatRestaurant(null);
  }, []);

  return (
    <div className="min-h-screen bg-cream text-ink">
      <Navbar />
      <Hero />
      <DishSearch
        onOpenChat={openChat}
        restaurantPhotoMap={restaurantPhotoMap}
        restaurantGeoMap={restaurantGeoMap}
        userLoc={userLoc}
        locDenied={locDenied}
        onRequestLocation={requestLocation}
      />
      <DiscoveryModes onOpenChat={openChat} restaurantGeoMap={restaurantGeoMap} />
      <Footer />
      {chatRestaurant && (
        <ChatPanel
          slug={chatRestaurant.slug}
          name={chatRestaurant.name}
          onClose={closeChat}
        />
      )}
    </div>
  );
}
