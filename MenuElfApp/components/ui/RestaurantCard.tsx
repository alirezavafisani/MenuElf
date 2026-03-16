import React, { useRef } from 'react';
import { View, Text, TouchableOpacity, Animated, StyleSheet } from 'react-native';
import { colors, radii, spacing } from '../../lib/theme';
import MatchBadge from './MatchBadge';

type Props = {
  name: string;
  cuisineType?: string;
  matchScore?: number | null;
  topDish?: string | null;
  topDishPrice?: number | null;
  rating?: number | null;
  reviews?: number | null;
  onPress: () => void;
};

export default function RestaurantCard({
  name, cuisineType, matchScore, topDish, topDishPrice,
  rating, reviews, onPress,
}: Props) {
  const scale = useRef(new Animated.Value(1)).current;

  const onPressIn = () => {
    Animated.spring(scale, { toValue: 0.98, useNativeDriver: true, friction: 5 }).start();
  };
  const onPressOut = () => {
    Animated.spring(scale, { toValue: 1, useNativeDriver: true, friction: 5 }).start();
  };

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.9}
        onPress={onPress}
        onPressIn={onPressIn}
        onPressOut={onPressOut}
      >
        <View style={styles.topRow}>
          <View style={styles.nameSection}>
            <Text style={styles.name} numberOfLines={1}>{name}</Text>
            {cuisineType ? <Text style={styles.cuisine}>{cuisineType}</Text> : null}
          </View>
          {matchScore != null && <MatchBadge score={matchScore} />}
        </View>

        {topDish && (
          <Text style={styles.topDish} numberOfLines={1}>
            Try the {topDish}{topDishPrice ? ` ($${topDishPrice.toFixed(0)})` : ''}
          </Text>
        )}

        <View style={styles.metaRow}>
          {rating != null && (
            <View style={styles.ratingContainer}>
              <Text style={styles.ratingStar}>&#9733;</Text>
              <Text style={styles.ratingText}>{rating}</Text>
              {reviews != null && <Text style={styles.reviewCount}>({reviews})</Text>}
            </View>
          )}
        </View>
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.cardPadding,
    marginBottom: spacing.cardGap,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  nameSection: {
    flex: 1,
    marginRight: 8,
  },
  name: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  cuisine: {
    fontSize: 12,
    color: colors.textTertiary,
    marginTop: 2,
  },
  topDish: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.goldPrimary,
    marginTop: 8,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  ratingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  ratingStar: {
    fontSize: 14,
    color: colors.goldPrimary,
    marginRight: 3,
  },
  ratingText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  reviewCount: {
    fontSize: 12,
    color: colors.textTertiary,
    marginLeft: 4,
  },
});
