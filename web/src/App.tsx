import { useState, useCallback, useEffect, useMemo } from 'react';
import { getRestaurants } from './api';
import type { Restaurant } from './types';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import DishSearch from './components/DishSearch';
import RestaurantMap from './components/RestaurantMap';
import ChatPanel from './components/ChatPanel';
import Footer from './components/Footer';

export default function App() {
  const [chatRestaurant, setChatRestaurant] = useState<{
    slug: string;
    name: string;
  } | null>(null);

  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);

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

  const openChat = useCallback((slug: string, name: string) => {
    setChatRestaurant({ slug, name });
  }, []);

  const closeChat = useCallback(() => {
    setChatRestaurant(null);
  }, []);

  return (
    <div className="min-h-screen bg-bg">
      <Navbar />
      <Hero />
      <DishSearch onOpenChat={openChat} restaurantPhotoMap={restaurantPhotoMap} />
      <RestaurantMap onOpenChat={openChat} restaurants={restaurants} />
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
