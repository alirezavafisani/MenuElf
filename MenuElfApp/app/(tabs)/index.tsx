import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet, View, Text, TouchableOpacity, Image,
  ActivityIndicator, ScrollView, FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { apiGet, logInteraction } from '../../lib/api';
import { colors, radii, spacing, shadows, getMatchColor } from '../../lib/theme';
import Header from '../../components/ui/Header';
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

type Mood = 'everyday' | 'treat' | 'healthy';

export default function ForYouScreen() {
  const router = useRouter();
  const [restaurants, setRestaurants] = useState<RestaurantInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [heroResult, setHeroResult] = useState<RestaurantInfo | null>(null);
  const [heroLoading, setHeroLoading] = useState(false);
  const [mood, setMood] = useState<Mood>('everyday');

  const fetchRestaurants = useCallback(async () => {
    try {
      const res = await apiGet('/restaurants?q=');
      if (res.ok) {
        const data = await res.json();
        setRestaurants(data.restaurants || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchRestaurants(); }, [fetchRestaurants]);

  const topRestaurants = [...restaurants]
    .sort((a, b) => (b.match_score ?? b.rating ?? 0) - (a.match_score ?? a.rating ?? 0))
    .slice(0, 10);

  const handleWhatShouldIEat = () => {
    setHeroLoading(true);
    const candidates = topRestaurants.length > 0 ? topRestaurants : restaurants;
    if (candidates.length === 0) {
      setHeroLoading(false);
      return;
    }
    const randomIdx = Math.floor(Math.random() * Math.min(candidates.length, 5));
    const pick = candidates[randomIdx];
    logInteraction('what_should_i_eat', { restaurant_slug: pick.slug, mood });
    setTimeout(() => {
      setHeroResult(pick);
      setHeroLoading(false);
    }, 600);
  };

  const openChat = (slug: string) => {
    logInteraction('restaurant_tap', { restaurant_slug: slug });
    router.push(`/chat?restaurant=${encodeURIComponent(slug)}`);
  };

  const renderHorizontalCard = ({ item }: { item: RestaurantInfo }) => {
    const photoUrl = item.photos && item.photos.length > 0 ? item.photos[0] : null;
    return (
      <TouchableOpacity
        style={styles.hCard}
        activeOpacity={0.9}
        onPress={() => openChat(item.slug)}
      >
        {photoUrl && (
          <Image source={{ uri: photoUrl }} style={styles.hCardPhoto} />
        )}
        {!photoUrl && (
          <View style={[styles.hCardPhoto, styles.hCardPhotoPlaceholder]}>
            <Text style={styles.hCardPlaceholderEmoji}>&#127860;</Text>
          </View>
        )}
        <View style={styles.hCardContent}>
          <Text style={styles.hCardName} numberOfLines={1}>{item.name}</Text>
          {item.match_score != null && (
            <Text style={[styles.hCardMatch, { color: getMatchColor(item.match_score) }]}>
              {item.match_score}% match
            </Text>
          )}
          {item.top_dish?.dish_name && (
            <Text style={styles.hCardDish} numberOfLines={1}>{item.top_dish.dish_name}</Text>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <Header />
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Hero Button */}
        <View style={styles.heroSection}>
          <TouchableOpacity
            style={styles.heroButton}
            activeOpacity={0.85}
            onPress={handleWhatShouldIEat}
            disabled={heroLoading || isLoading}
          >
            {heroLoading ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <Text style={styles.heroButtonText}>What Should I Eat?</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Hero Result */}
        {heroResult && (
          <View style={styles.heroResultCard}>
            {heroResult.photos && heroResult.photos.length > 0 && (
              <Image source={{ uri: heroResult.photos[0] }} style={styles.heroResultPhoto} />
            )}
            <View style={styles.heroResultContent}>
              <View style={styles.heroResultRow}>
                <Text style={styles.heroResultName}>{heroResult.name}</Text>
                {heroResult.match_score != null && (
                  <Text style={[styles.heroResultMatch, { color: getMatchColor(heroResult.match_score) }]}>
                    {heroResult.match_score}%
                  </Text>
                )}
              </View>
              {heroResult.top_dish?.dish_name && (
                <Text style={styles.heroResultDish}>
                  {heroResult.top_dish.dish_name}
                  {heroResult.top_dish.price ? ` · $${heroResult.top_dish.price.toFixed(0)}` : ''}
                </Text>
              )}
              {heroResult.address && (
                <Text style={styles.heroResultAddress} numberOfLines={1}>{heroResult.address}</Text>
              )}
              <View style={styles.heroResultActions}>
                <TouchableOpacity onPress={handleWhatShouldIEat}>
                  <Text style={styles.tryAnother}>Try Another</Text>
                </TouchableOpacity>
                <AccentButton
                  title="Open Chat"
                  onPress={() => openChat(heroResult.slug)}
                  inline
                  style={{ paddingHorizontal: 20 }}
                />
              </View>
            </View>
          </View>
        )}

        {/* Mood Toggle */}
        <View style={styles.moodSection}>
          {(['everyday', 'treat', 'healthy'] as Mood[]).map((m) => (
            <TouchableOpacity
              key={m}
              style={[styles.moodPill, mood === m && styles.moodPillActive]}
              onPress={() => setMood(m)}
            >
              <Text style={[styles.moodText, mood === m && styles.moodTextActive]}>
                {m === 'everyday' ? 'Everyday' : m === 'treat' ? 'Treat Yourself' : 'Healthy'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* For You Section */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>For You</Text>
        </View>

        {isLoading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.accent} />
          </View>
        ) : topRestaurants.length > 0 ? (
          <FlatList
            data={topRestaurants}
            keyExtractor={(item, idx) => `${item.slug}-${idx}`}
            renderItem={renderHorizontalCard}
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.hCardList}
            scrollEnabled
          />
        ) : (
          <Text style={styles.emptyText}>No recommendations yet</Text>
        )}

        {/* Friends Are Eating */}
        <View style={[styles.sectionHeader, { marginTop: spacing.sectionGap }]}>
          <Text style={styles.sectionTitle}>Friends Are Eating</Text>
        </View>
        <View style={styles.comingSoonCard}>
          <Text style={styles.comingSoonText}>Coming soon</Text>
          <Text style={styles.comingSoonSubtext}>See what your friends are enjoying</Text>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scrollContent: { paddingBottom: 20 },

  heroSection: {
    paddingHorizontal: spacing.screenPadding,
    paddingTop: 8,
    paddingBottom: 20,
  },
  heroButton: {
    backgroundColor: colors.accent,
    borderRadius: radii.button,
    paddingVertical: 20,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadows.elevated,
  },
  heroButtonText: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '700',
  },

  heroResultCard: {
    marginHorizontal: spacing.screenPadding,
    marginBottom: 24,
    borderRadius: radii.card,
    backgroundColor: colors.background,
    overflow: 'hidden',
    ...shadows.elevated,
  },
  heroResultPhoto: {
    width: '100%',
    height: 180,
    backgroundColor: colors.backgroundTertiary,
  },
  heroResultContent: {
    padding: spacing.cardPadding,
  },
  heroResultRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  heroResultName: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
    flex: 1,
    marginRight: 8,
  },
  heroResultMatch: {
    fontSize: 16,
    fontWeight: '800',
  },
  heroResultDish: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.accent,
    marginTop: 6,
  },
  heroResultAddress: {
    fontSize: 13,
    color: colors.textTertiary,
    marginTop: 4,
  },
  heroResultActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
  },
  tryAnother: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
  },

  moodSection: {
    flexDirection: 'row',
    paddingHorizontal: spacing.screenPadding,
    gap: 10,
    marginBottom: spacing.sectionGap,
  },
  moodPill: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  moodPillActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  moodText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  moodTextActive: {
    color: '#FFFFFF',
  },

  sectionHeader: {
    paddingHorizontal: spacing.screenPadding,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
  },

  loadingContainer: {
    paddingVertical: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 15,
    color: colors.textTertiary,
    textAlign: 'center',
    paddingVertical: 20,
  },

  hCardList: {
    paddingHorizontal: spacing.screenPadding,
    gap: 12,
  },
  hCard: {
    width: 200,
    borderRadius: radii.card,
    backgroundColor: colors.background,
    overflow: 'hidden',
    ...shadows.card,
  },
  hCardPhoto: {
    width: 200,
    height: 120,
    backgroundColor: colors.backgroundTertiary,
  },
  hCardPhotoPlaceholder: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  hCardPlaceholderEmoji: {
    fontSize: 32,
  },
  hCardContent: {
    padding: 12,
  },
  hCardName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  hCardMatch: {
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 2,
  },
  hCardDish: {
    fontSize: 13,
    color: colors.textSecondary,
  },

  comingSoonCard: {
    marginHorizontal: spacing.screenPadding,
    backgroundColor: colors.backgroundSecondary,
    borderRadius: radii.card,
    padding: 24,
    alignItems: 'center',
  },
  comingSoonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 4,
  },
  comingSoonSubtext: {
    fontSize: 14,
    color: colors.textTertiary,
  },
});
