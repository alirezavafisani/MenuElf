import { useState, useCallback } from 'react';
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
      <DishSearch onOpenChat={openChat} />
      <RestaurantMap onOpenChat={openChat} />
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
