import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity,
  ActivityIndicator, Platform, Animated, FlatList, Keyboard,
} from 'react-native';
import { useRouter } from 'expo-router';
import MapView, { Marker, Callout, PROVIDER_GOOGLE } from '../../components/MapView';
import * as Location from 'expo-location';
import { API_URL } from '../../lib/config';

type RestaurantInfo = {
  name: string;
  slug: string;
  lat: number | null;
  lng: number | null;
  rating: number | null;
  reviews: number | null;
  address: string | null;
};

// ── Rating → color helper ────────────────────────────
const ratingColor = (r: number | null) => {
  if (!r) return '#999';
  if (r >= 4.5) return '#27AE60';
  if (r >= 4.0) return '#F39C12';
  if (r >= 3.0) return '#E67E22';
  return '#E74C3C';
};

// ── Component ────────────────────────────────────────
export default function SearchScreen() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [restaurants, setRestaurants] = useState<RestaurantInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedRestaurant, setSelectedRestaurant] = useState<RestaurantInfo | null>(null);
  const [userLocation, setUserLocation] = useState<{ latitude: number; longitude: number } | null>(null);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [markersReady, setMarkersReady] = useState(false);
  const mapRef = useRef<any>(null);
  const cardAnim = useRef(new Animated.Value(0)).current;

  // Let markers render fully before turning off tracking (Android fix)
  // Reset whenever restaurants change (e.g. after search) so new markers render properly
  useEffect(() => {
    setMarkersReady(false);
    const timer = setTimeout(() => setMarkersReady(true), 2000);
    return () => clearTimeout(timer);
  }, [restaurants]);

  // ── Get user location ──────────────────────────────
  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
        setUserLocation({ latitude: loc.coords.latitude, longitude: loc.coords.longitude });
      }
    })();
  }, []);

  // ── Fetch restaurants ──────────────────────────────
  const fetchRestaurants = useCallback(async (query: string = '') => {
    try {
      setError('');
      const res = await fetch(`${API_URL}/restaurants?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Network response was not ok');
      const data = await res.json();
      setRestaurants(data.restaurants || []);
    } catch (err) {
      console.error(err);
      setError('Something went wrong connecting to the backend.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchRestaurants(''); }, [fetchRestaurants]);

  // ── Debounced search ───────────────────────────────
  useEffect(() => {
    const timer = setTimeout(() => fetchRestaurants(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, fetchRestaurants]);

  // ── Animate bottom card ────────────────────────────
  useEffect(() => {
    Animated.spring(cardAnim, {
      toValue: selectedRestaurant ? 1 : 0,
      useNativeDriver: true,
      friction: 8,
    }).start();
  }, [selectedRestaurant]);

  // ── Center map on user location ────────────────────
  useEffect(() => {
    if (userLocation && mapRef.current) {
      mapRef.current.animateToRegion?.({
        ...userLocation,
        latitudeDelta: 0.025,
        longitudeDelta: 0.025,
      }, 800);
    }
  }, [userLocation]);

  // ── Handlers ───────────────────────────────────────
  const onMarkerPress = (item: RestaurantInfo) => {
    setSelectedRestaurant(item);
    setIsSearchFocused(false);
    Keyboard.dismiss();
  };

  const openChat = (slug: string) => {
    router.push(`/chat?restaurant=${encodeURIComponent(slug)}`);
  };

  const onSearchItemPress = (item: RestaurantInfo) => {
    setSearchQuery('');
    setIsSearchFocused(false);
    Keyboard.dismiss();
    // If the restaurant has coordinates, zoom to it and select it
    if (item.lat && item.lng) {
      mapRef.current?.animateToRegion?.({
        latitude: item.lat,
        longitude: item.lng,
        latitudeDelta: 0.008,
        longitudeDelta: 0.008,
      }, 600);
      setSelectedRestaurant(item);
    } else {
      // If no coordinates, go straight to chat
      openChat(item.slug);
    }
  };

  // ── Render ─────────────────────────────────────────
  const initialRegion = userLocation
    ? { ...userLocation, latitudeDelta: 0.025, longitudeDelta: 0.025 }
    : { latitude: 51.0447, longitude: -114.0719, latitudeDelta: 0.06, longitudeDelta: 0.06 };

  const cardTranslateY = cardAnim.interpolate({ inputRange: [0, 1], outputRange: [200, 0] });

  const showDropdown = isSearchFocused && searchQuery.trim().length > 0;

  return (
    <View style={styles.container}>
      {/* ── Search Bar + Dropdown ───────────────────── */}
      <View style={styles.searchOverlay}>
        <TextInput
          style={styles.searchInput}
          placeholder="🔍  Search restaurants..."
          placeholderTextColor="#999"
          value={searchQuery}
          onChangeText={(t) => { setSearchQuery(t); setSelectedRestaurant(null); }}
          onFocus={() => setIsSearchFocused(true)}
          clearButtonMode="while-editing"
        />

        {/* ── Search Results Dropdown ──────────────── */}
        {showDropdown && (
          <View style={styles.dropdown}>
            <FlatList
              data={restaurants.slice(0, 8)}
              keyExtractor={(item, idx) => `${item.slug}-${idx}`}
              keyboardShouldPersistTaps="handled"
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={styles.dropdownItem}
                  onPress={() => onSearchItemPress(item)}
                  activeOpacity={0.7}
                >
                  <View style={styles.dropdownLeft}>
                    <View style={[styles.dropdownDot, { backgroundColor: ratingColor(item.rating) }]} />
                    <Text style={styles.dropdownName} numberOfLines={1}>{item.name}</Text>
                  </View>
                  {item.rating ? (
                    <Text style={styles.dropdownRating}>⭐ {item.rating}</Text>
                  ) : null}
                </TouchableOpacity>
              )}
              ListEmptyComponent={
                <View style={styles.dropdownEmpty}>
                  <Text style={styles.dropdownEmptyText}>No restaurants found</Text>
                </View>
              }
            />
          </View>
        )}
      </View>

      {/* ── Map ────────────────────────────────────── */}
      {isLoading ? (
        <View style={styles.centerBox}>
          <ActivityIndicator size="large" color="#D4754E" />
          <Text style={styles.loadingText}>Loading restaurants…</Text>
        </View>
      ) : error ? (
        <View style={styles.centerBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : (
        <MapView
          ref={mapRef}
          style={styles.map}
          provider={PROVIDER_GOOGLE}
          initialRegion={initialRegion}
          showsUserLocation
          showsMyLocationButton
          followsUserLocation
          showsCompass
          showsPointsOfInterest={false}
          onPress={() => { setSelectedRestaurant(null); setIsSearchFocused(false); Keyboard.dismiss(); }}
        >
          {restaurants.filter(r => r.lat != null && r.lng != null).map((item, idx) => (
            <Marker
              key={`${item.slug}-${idx}`}
              coordinate={{ latitude: item.lat!, longitude: item.lng! }}
              onPress={() => onMarkerPress(item)}
              tracksViewChanges={!markersReady}
            >
              <View style={styles.markerOuter}>
                <View style={[styles.markerPill, { backgroundColor: ratingColor(item.rating) }]}>
                  <Text style={styles.markerIcon}>🍴</Text>
                  {item.rating ? (
                    <Text style={styles.markerScore}>{item.rating}</Text>
                  ) : null}
                </View>
                <View style={[styles.markerArrow, { borderTopColor: ratingColor(item.rating) }]} />
              </View>
            </Marker>
          ))}
        </MapView>
      )}

      {/* ── Bottom Card ────────────────────────────── */}
      <Animated.View
        style={[styles.bottomCard, { transform: [{ translateY: cardTranslateY }] }]}
        pointerEvents={selectedRestaurant ? 'auto' : 'none'}
      >
        {selectedRestaurant && (
          <>
            <Text style={styles.cardName}>{selectedRestaurant.name}</Text>
            <View style={styles.cardMeta}>
              {selectedRestaurant.rating ? (
                <View style={styles.ratingBadge}>
                  <Text style={styles.ratingBadgeText}>⭐ {selectedRestaurant.rating}</Text>
                  <Text style={styles.reviewCount}>({selectedRestaurant.reviews})</Text>
                </View>
              ) : null}
              {selectedRestaurant.address ? (
                <Text style={styles.addressText} numberOfLines={1}>{selectedRestaurant.address}</Text>
              ) : null}
            </View>
            <TouchableOpacity
              style={styles.chatBtn}
              onPress={() => openChat(selectedRestaurant.slug)}
              activeOpacity={0.8}
            >
              <Text style={styles.chatBtnText}>Chat with menu 💬</Text>
            </TouchableOpacity>
          </>
        )}
      </Animated.View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },

  // Search
  searchOverlay: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 54 : 36,
    left: 16,
    right: 16,
    zIndex: 20,
  },
  searchInput: {
    backgroundColor: '#FFF',
    borderRadius: 14,
    paddingHorizontal: 18,
    paddingVertical: 14,
    fontSize: 16,
    color: '#1A1A1A',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 6,
  },

  // Dropdown
  dropdown: {
    backgroundColor: '#FFF',
    borderRadius: 14,
    marginTop: 6,
    maxHeight: 320,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
    overflow: 'hidden',
  },
  dropdownItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#F0EBE6',
  },
  dropdownLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 8,
  },
  dropdownDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 12,
  },
  dropdownName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#1A1A1A',
    flex: 1,
  },
  dropdownRating: {
    fontSize: 13,
    fontWeight: '600',
    color: '#F39C12',
  },
  dropdownEmpty: {
    paddingVertical: 20,
    alignItems: 'center',
  },
  dropdownEmptyText: {
    fontSize: 14,
    color: '#999',
  },

  // Map
  map: { flex: 1 },
  centerBox: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: 12, fontSize: 15, color: '#7A7A7A' },
  errorText: { color: '#D4754E', fontSize: 16, textAlign: 'center', paddingHorizontal: 24 },

  // ── Map Marker ────────────────────────────────────
  markerOuter: {
    alignItems: 'center',
  },
  markerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 22,
    borderWidth: 3,
    borderColor: '#FFFFFF',
    minWidth: 56,
    height: 42,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 6,
    elevation: 8,
  },
  markerIcon: {
    fontSize: 20,
  },
  markerScore: {
    fontSize: 15,
    fontWeight: '900',
    color: '#FFF',
    marginLeft: 3,
    textShadowColor: 'rgba(0,0,0,0.3)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  markerArrow: {
    width: 0,
    height: 0,
    borderLeftWidth: 9,
    borderRightWidth: 9,
    borderTopWidth: 12,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    marginTop: -2,
  },

  // Bottom card
  bottomCard: {
    position: 'absolute',
    bottom: 100,
    left: 16,
    right: 16,
    backgroundColor: '#FFF',
    borderRadius: 20,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 10,
  },
  cardName: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1A1A1A',
    marginBottom: 8,
  },
  cardMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
    gap: 10,
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF8E1',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  ratingBadgeText: { fontSize: 14, fontWeight: '700', color: '#F39C12' },
  reviewCount: { fontSize: 12, color: '#999', marginLeft: 4 },
  addressText: { fontSize: 13, color: '#777', flex: 1 },

  chatBtn: {
    backgroundColor: '#D4754E',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
  },
  chatBtnText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '700',
  },
});
