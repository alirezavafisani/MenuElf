import React, { useRef } from 'react';
import { Animated, TouchableOpacity, StyleSheet, ViewStyle } from 'react-native';
import { colors, radii, spacing } from '../../lib/theme';

type Props = {
  children: React.ReactNode;
  onPress?: () => void;
  elevated?: boolean;
  style?: ViewStyle;
};

export default function Card({ children, onPress, elevated, style }: Props) {
  const scale = useRef(new Animated.Value(1)).current;

  const onPressIn = () => {
    if (onPress) Animated.spring(scale, { toValue: 0.98, useNativeDriver: true, friction: 5 }).start();
  };
  const onPressOut = () => {
    if (onPress) Animated.spring(scale, { toValue: 1, useNativeDriver: true, friction: 5 }).start();
  };

  const content = (
    <Animated.View style={[
      styles.card,
      elevated && styles.elevated,
      { transform: [{ scale }] },
      style,
    ]}>
      {children}
    </Animated.View>
  );

  if (onPress) {
    return (
      <TouchableOpacity
        activeOpacity={0.9}
        onPress={onPress}
        onPressIn={onPressIn}
        onPressOut={onPressOut}
      >
        {content}
      </TouchableOpacity>
    );
  }

  return content;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.cardPadding,
  },
  elevated: {
    backgroundColor: colors.surfaceElevated,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
});
