import React, { useState, useEffect } from 'react';
import {
  StyleSheet, View, Text, TouchableOpacity,
  FlatList, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiGet, apiPost } from '../../lib/api';
import { colors, radii, spacing, shadows, getMatchColor } from '../../lib/theme';
import GoldButton from '../../components/ui/GoldButton';

type PerMember = {
  user_id: string;
  display_name: string;
  avatar_emoji: string;
  match_score: number;
  top_dish?: {
    dish_name: string;
    price: number | null;
    match_reason: string;
  } | null;
};

type RestaurantRec = {
  slug: string;
  name: string;
  group_match_score: number;
  per_member: PerMember[];
};

export default function GroupRecommendationsScreen() {
  const { planId } = useLocalSearchParams<{ planId: string }>();
  const router = useRouter();

  const [restaurants, setRestaurants] = useState<RestaurantRec[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [choosingSlug, setChoosingSlug] = useState<string | null>(null);

  useEffect(() => { if (planId) loadRecs(); }, [planId]);

  const loadRecs = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiGet(`/plans/${planId}/recommendations`);
      if (res.ok) { const data = await res.json(); setRestaurants(data.restaurants ?? []); }
      else { setError('Could not load recommendations'); }
    } catch { setError('Network error. Check your connection.'); }
    finally { setLoading(false); }
  };

  const handleChoose = async (slug: string, name: string) => {
    Alert.alert('Choose Restaurant', `Decide on ${name} for the group?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Choose',
        onPress: async () => {
          setChoosingSlug(slug);
          try {
            const res = await apiPost(`/plans/${planId}/decide`, { restaurant_slug: slug });
            if (res.ok) router.back();
            else Alert.alert('Error', 'Could not decide restaurant');
          } catch { Alert.alert('Network error', 'Check your connection.'); }
          finally { setChoosingSlug(null); }
        },
      },
    ]);
  };

  const renderRestaurant = ({ item }: { item: RestaurantRec }) => {
    const scoreColor = getMatchColor(item.group_match_score);
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.cardHeaderLeft}>
            <Text style={styles.restaurantName}>{item.name}</Text>
          </View>
          <View style={[styles.scoreBadge, { backgroundColor: item.group_match_score >= 80 ? colors.accentLight : colors.backgroundTertiary }]}>
            <Text style={[styles.scoreText, { color: scoreColor }]}>{item.group_match_score}%</Text>
          </View>
        </View>

        <View style={styles.memberDishes}>
          {item.per_member.map(member => (
            <View key={member.user_id} style={styles.memberRow}>
              <Text style={styles.memberEmoji}>{member.avatar_emoji}</Text>
              <View style={styles.memberDishInfo}>
                <Text style={styles.memberName}>{member.display_name}</Text>
                {member.top_dish ? (
                  <Text style={styles.memberDish} numberOfLines={1}>
                    {member.top_dish.dish_name}
                    {member.top_dish.price != null ? ` · $${member.top_dish.price.toFixed(0)}` : ''}
                  </Text>
                ) : (
                  <Text style={styles.memberDishEmpty}>No specific dish</Text>
                )}
              </View>
              <Text style={[styles.memberScore, { color: getMatchColor(member.match_score) }]}>
                {member.match_score}%
              </Text>
            </View>
          ))}
        </View>

        <GoldButton
          title={choosingSlug === item.slug ? 'Choosing...' : 'Choose This'}
          onPress={() => handleChoose(item.slug, item.name)}
          loading={choosingSlug === item.slug}
          disabled={choosingSlug !== null}
        />
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Restaurants for the Group</Text>
        <View style={{ width: 44 }} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={styles.loadingText}>Finding the best spots...</Text>
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
          <View style={{ marginTop: 12, width: 160 }}>
            <GoldButton title="Retry" onPress={loadRecs} />
          </View>
        </View>
      ) : restaurants.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyText}>No recommendations available yet</Text>
          <Text style={styles.emptySubtext}>
            Make sure at least 2 members have joined and completed onboarding
          </Text>
        </View>
      ) : (
        <FlatList
          data={restaurants}
          keyExtractor={item => item.slug}
          renderItem={renderRestaurant}
          contentContainerStyle={styles.listContent}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },

  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: spacing.screenPadding, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  backBtn: { width: 44, padding: 8 },
  headerTitle: { flex: 1, fontSize: 17, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },

  listContent: { padding: spacing.screenPadding, paddingBottom: 40 },
  card: {
    backgroundColor: colors.background, borderRadius: radii.card,
    padding: spacing.cardPadding, marginBottom: spacing.cardGap, ...shadows.card,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  cardHeaderLeft: { flex: 1, marginRight: 8 },
  restaurantName: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
  scoreBadge: { borderRadius: radii.pill, paddingHorizontal: 10, paddingVertical: 4 },
  scoreText: { fontSize: 14, fontWeight: '800' },

  memberDishes: { marginBottom: 14, gap: 8 },
  memberRow: { flexDirection: 'row', alignItems: 'center' },
  memberEmoji: { fontSize: 20, marginRight: 10, width: 28 },
  memberDishInfo: { flex: 1 },
  memberName: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  memberDish: { fontSize: 14, color: colors.accent, marginTop: 1 },
  memberDishEmpty: { fontSize: 13, color: colors.textTertiary, fontStyle: 'italic', marginTop: 1 },
  memberScore: { fontSize: 13, fontWeight: '700', marginLeft: 8 },

  loadingText: { fontSize: 15, color: colors.textSecondary, marginTop: 12 },
  errorText: { fontSize: 16, color: colors.error, textAlign: 'center' },
  emptyText: { fontSize: 18, fontWeight: '600', color: colors.textSecondary, marginBottom: 8 },
  emptySubtext: { fontSize: 14, color: colors.textTertiary, textAlign: 'center', lineHeight: 20 },
});
