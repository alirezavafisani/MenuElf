import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  StyleSheet, View, Text, TouchableOpacity,
  ActivityIndicator, Platform, Animated, FlatList, Keyboard,
} from 'react-native';
import { useRouter } from 'expo-router';
import MapView, { Marker, PROVIDER_GOOGLE } from '../../components/MapView';
import * as Location from 'expo-location';
import { apiGet, logInteraction } from '../../lib/api';
import { colors, radii, spacing, shadows, getMatchColor } from '../../lib/theme';
import SearchBar from '../../components/ui/SearchBar';
import MatchBadge from '../../components/ui/MatchBadge';
import AccentButton from '../../components/ui/AccentButton';

type TopDish = {
  dish_name: string;
  price: number | null;
  match_reason: string;
};

type RestaurantInfo = {
  name: string;
  slug: string;
  lat: number | null;
  lng: number | null;
  rating: number | null;
  reviews: number | null;
  address: string | null;
  photos?: string[];
  match_score?: number;
  top_dish?: TopDish | null;
};

export default function ExploreScreen() {
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

  useEffect(() => {
    setMarkersReady(false);
    const timer = setTimeout(() => setMarkersReady(true), 2000);
    return () => clearTimeout(timer);
  }, [restaurants]);

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
        setUserLocation({ latitude: loc.coords.latitude, longitude: loc.coords.longitude });
      }
    })();
  }, []);

  const fetchRestaurants = useCallback(async (query: string = '') => {
    try {
      setError('');
      const res = await apiGet(`/restaurants?q=${encodeURIComponent(query)}`);
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

  useEffect(() => {
    const timer = setTimeout(() => fetchRestaurants(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, fetchRestaurants]);

  useEffect(() => {
    Animated.spring(cardAnim, {
      toValue: selectedRestaurant ? 1 : 0,
      useNativeDriver: true,
      friction: 8,
    }).start();
  }, [selectedRestaurant]);

  useEffect(() => {
    if (userLocation && mapRef.current) {
      mapRef.current.animateToRegion?.({
        ...userLocation,
        latitudeDelta: 0.025,
        longitudeDelta: 0.025,
      }, 800);
    }
  }, [userLocation]);

  const onMarkerPress = (item: RestaurantInfo) => {
    setSelectedRestaurant(item);
    setIsSearchFocused(false);
    Keyboard.dismiss();
  };

  const openChat = (slug: string) => {
    logInteraction('restaurant_tap', { restaurant_slug: slug });
    router.push(`/chat?restaurant=${encodeURIComponent(slug)}`);
  };

  const onSearchItemPress = (item: RestaurantInfo) => {
    setSearchQuery('');
    setIsSearchFocused(false);
    Keyboard.dismiss();
    if (item.lat && item.lng) {
      mapRef.current?.animateToRegion?.({
        latitude: item.lat,
        longitude: item.lng,
        latitudeDelta: 0.008,
        longitudeDelta: 0.008,
      }, 600);
      setSelectedRestaurant(item);
    } else {
      openChat(item.slug);
    }
  };

  const initialRegion = userLocation
    ? { ...userLocation, latitudeDelta: 0.025, longitudeDelta: 0.025 }
    : { latitude: 51.0447, longitude: -114.0719, latitudeDelta: 0.06, longitudeDelta: 0.06 };

  const cardTranslateY = cardAnim.interpolate({ inputRange: [0, 1], outputRange: [200, 0] });
  const showDropdown = isSearchFocused && searchQuery.trim().length > 0;

  return (
    <View style={styles.container}>
      {/* Search Bar */}
      <View style={styles.searchOverlay}>
        <SearchBar
          value={searchQuery}
          onChangeText={(t) => { setSearchQuery(t); setSelectedRestaurant(null); }}
          placeholder="Search restaurants..."
          onFocus={() => setIsSearchFocused(true)}
        />

        {/* Dropdown */}
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
                  <Text style={styles.dropdownName} numberOfLines={1}>{item.name}</Text>
                  <View style={styles.dropdownRight}>
                    {item.match_score != null && (
                      <Text style={[styles.dropdownMatch, { color: getMatchColor(item.match_score) }]}>
                        {item.match_score}%
                      </Text>
                    )}
                    {item.rating ? (
                      <Text style={styles.dropdownRating}>&#9733; {item.rating}</Text>
                    ) : null}
                  </View>
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

      {/* Map — NO dark style, default Google Maps */}
      {isLoading ? (
        <View style={styles.centerBox}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={styles.loadingText}>Loading restaurants...</Text>
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
                <View style={styles.markerPill}>
                  <Text style={styles.markerIcon}>&#127860;</Text>
                  {item.rating ? (
                    <Text style={styles.markerScore}>{item.rating}</Text>
                  ) : null}
                </View>
                <View style={styles.markerArrow} />
              </View>
            </Marker>
          ))}
        </MapView>
      )}

      {/* Bottom Card */}
      <Animated.View
        style={[styles.bottomCard, { transform: [{ translateY: cardTranslateY }] }]}
        pointerEvents={selectedRestaurant ? 'auto' : 'none'}
      >
        {selectedRestaurant && (
          <>
            <View style={styles.cardTopRow}>
              <Text style={styles.cardName} numberOfLines={1}>{selectedRestaurant.name}</Text>
              {selectedRestaurant.match_score != null && (
                <MatchBadge score={selectedRestaurant.match_score} />
              )}
            </View>
            <View style={styles.cardMeta}>
              {selectedRestaurant.rating ? (
                <View style={styles.ratingBadge}>
                  <Text style={styles.ratingStar}>&#9733;</Text>
                  <Text style={styles.ratingBadgeText}>{selectedRestaurant.rating}</Text>
                  {selectedRestaurant.reviews != null && (
                    <Text style={styles.reviewCount}>({selectedRestaurant.reviews})</Text>
                  )}
                </View>
              ) : null}
              {selectedRestaurant.address ? (
                <Text style={styles.addressText} numberOfLines={1}>{selectedRestaurant.address}</Text>
              ) : null}
            </View>
            {selectedRestaurant.top_dish?.dish_name && (
              <Text style={styles.topDishText} numberOfLines={1}>
                Try the {selectedRestaurant.top_dish.dish_name}
                {selectedRestaurant.top_dish.price ? ` ($${selectedRestaurant.top_dish.price.toFixed(0)})` : ''}
              </Text>
            )}
            <AccentButton
              title="Chat with menu"
              onPress={() => openChat(selectedRestaurant.slug)}
            />
          </>
        )}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },

  searchOverlay: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 54 : 36,
    left: spacing.screenPadding,
    right: spacing.screenPadding,
    zIndex: 20,
  },

  dropdown: {
    backgroundColor: colors.background,
    borderRadius: radii.card,
    marginTop: 6,
    maxHeight: 320,
    overflow: 'hidden',
    ...shadows.elevated,
  },
  dropdownItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  dropdownName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
    flex: 1,
    marginRight: 8,
  },
  dropdownRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dropdownRating: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.star,
  },
  dropdownMatch: {
    fontSize: 12,
    fontWeight: '700',
  },
  dropdownEmpty: {
    paddingVertical: 20,
    alignItems: 'center',
  },
  dropdownEmptyText: {
    fontSize: 14,
    color: colors.textTertiary,
  },

  map: { flex: 1 },
  centerBox: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  loadingText: { marginTop: 12, fontSize: 15, color: colors.textSecondary },
  errorText: { color: colors.error, fontSize: 16, textAlign: 'center', paddingHorizontal: 24 },

  markerOuter: { alignItems: 'center' },
  markerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 22,
    borderWidth: 2,
    borderColor: colors.accent,
    backgroundColor: colors.background,
    minWidth: 56,
    height: 42,
    ...shadows.card,
  },
  markerIcon: { fontSize: 18 },
  markerScore: {
    fontSize: 14,
    fontWeight: '900',
    color: colors.textPrimary,
    marginLeft: 3,
  },
  markerArrow: {
    width: 0,
    height: 0,
    borderLeftWidth: 8,
    borderRightWidth: 8,
    borderTopWidth: 10,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderTopColor: colors.accent,
    marginTop: -1,
  },

  bottomCard: {
    position: 'absolute',
    bottom: 100,
    left: spacing.screenPadding,
    right: spacing.screenPadding,
    backgroundColor: colors.background,
    borderRadius: radii.card,
    padding: spacing.cardPadding,
    ...shadows.elevated,
  },
  cardTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  cardName: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
    flex: 1,
    marginRight: 8,
  },
  cardMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 10,
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  ratingStar: {
    fontSize: 14,
    color: colors.star,
    marginRight: 3,
  },
  ratingBadgeText: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  reviewCount: { fontSize: 12, color: colors.textTertiary, marginLeft: 4 },
  addressText: { fontSize: 13, color: colors.textSecondary, flex: 1 },
  topDishText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.accent,
    marginBottom: 12,
  },
});
