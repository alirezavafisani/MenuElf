import React, { useRef } from 'react';
import { View, Text, TouchableOpacity, Animated, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, spacing, shadows } from '../../lib/theme';

type Props = {
  name: string;
  price: number | null;
  description?: string;
  restaurantName?: string;
  matchReason?: string;
  category?: string;
  dietaryTags?: string[];
  onPress?: () => void;
  onSave?: () => void;
  saved?: boolean;
};

export default function DishCard({
  name, price, description, restaurantName, matchReason,
  category, dietaryTags, onPress, onSave, saved,
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
          <Text style={styles.name} numberOfLines={1}>{name}</Text>
          <View style={styles.rightSection}>
            <Text style={styles.price}>
              {price != null ? `$${price.toFixed(2)}` : ''}
            </Text>
            {onSave && (
              <TouchableOpacity onPress={onSave} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                <Ionicons
                  name={saved ? 'heart' : 'heart-outline'}
                  size={20}
                  color={saved ? colors.accent : colors.textTertiary}
                />
              </TouchableOpacity>
            )}
          </View>
        </View>

        {restaurantName ? (
          <Text style={styles.restaurant}>{restaurantName}</Text>
        ) : null}

        {description ? (
          <Text style={styles.description} numberOfLines={2}>{description}</Text>
        ) : null}

        {matchReason ? (
          <Text style={styles.matchReason}>{matchReason}</Text>
        ) : null}

        {(category || (dietaryTags && dietaryTags.length > 0)) && (
          <View style={styles.tagsRow}>
            {category ? (
              <View style={styles.categoryBadge}>
                <Text style={styles.categoryText}>{category}</Text>
              </View>
            ) : null}
            {dietaryTags?.map((tag, i) => (
              <View key={i} style={styles.dietaryBadge}>
                <Text style={styles.dietaryText}>{tag}</Text>
              </View>
            ))}
          </View>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.background,
    borderRadius: radii.card,
    padding: spacing.cardPadding,
    marginBottom: spacing.cardGap,
    ...shadows.card,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  name: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    flex: 1,
    marginRight: 8,
  },
  rightSection: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  price: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.accent,
  },
  restaurant: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 4,
  },
  description: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: 4,
  },
  matchReason: {
    fontSize: 13,
    color: colors.accent,
    fontStyle: 'italic',
    marginTop: 4,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 8,
  },
  categoryBadge: {
    backgroundColor: colors.backgroundTertiary,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  categoryText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
  },
  dietaryBadge: {
    backgroundColor: 'rgba(52,168,83,0.1)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  dietaryText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.success,
    textTransform: 'uppercase',
  },
});
