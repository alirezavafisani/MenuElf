import React, { useRef } from 'react';
import {
  TouchableOpacity, Text, ActivityIndicator, Animated,
  StyleSheet, ViewStyle, TextStyle,
} from 'react-native';
import { colors, radii } from '../../lib/theme';

type Props = {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  inline?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
};

export default function GoldButton({ title, onPress, loading, disabled, inline, style, textStyle }: Props) {
  const scale = useRef(new Animated.Value(1)).current;

  const onPressIn = () => {
    Animated.spring(scale, { toValue: 0.97, useNativeDriver: true, friction: 5 }).start();
  };
  const onPressOut = () => {
    Animated.spring(scale, { toValue: 1, useNativeDriver: true, friction: 5 }).start();
  };

  return (
    <Animated.View style={[{ transform: [{ scale }] }, inline ? styles.inline : styles.full, style]}>
      <TouchableOpacity
        style={[styles.button, (disabled || loading) && styles.disabled]}
        onPress={onPress}
        onPressIn={onPressIn}
        onPressOut={onPressOut}
        disabled={disabled || loading}
        activeOpacity={0.8}
      >
        {loading ? (
          <ActivityIndicator color="#FFFFFF" size="small" />
        ) : (
          <Text style={[styles.text, textStyle]}>{title}</Text>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  full: { width: '100%' },
  inline: { alignSelf: 'flex-start' },
  button: {
    backgroundColor: colors.goldDark,
    borderRadius: radii.input,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disabled: { opacity: 0.5 },
  text: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
});
