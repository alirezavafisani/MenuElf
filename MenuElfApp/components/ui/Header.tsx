import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing } from '../../lib/theme';

type Props = {
  title?: string;
  rightIcon?: keyof typeof Ionicons.glyphMap;
  onRightPress?: () => void;
  showBack?: boolean;
  onBack?: () => void;
};

export default function Header({ title, rightIcon, onRightPress, showBack, onBack }: Props) {
  return (
    <View style={styles.container}>
      {showBack ? (
        <TouchableOpacity style={styles.backBtn} onPress={onBack}>
          <Ionicons name="arrow-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
      ) : (
        <Text style={styles.logo}>MenuElf</Text>
      )}

      {title ? <Text style={styles.title} numberOfLines={1}>{title}</Text> : <View style={{ flex: 1 }} />}

      {rightIcon ? (
        <TouchableOpacity style={styles.rightBtn} onPress={onRightPress}>
          <Ionicons name={rightIcon} size={22} color={colors.textSecondary} />
        </TouchableOpacity>
      ) : (
        <View style={{ width: 40 }} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.screenPadding,
    paddingVertical: 12,
    backgroundColor: 'transparent',
  },
  logo: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.textPrimary,
    width: 90,
  },
  title: {
    flex: 1,
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  backBtn: {
    width: 40,
    padding: 4,
  },
  rightBtn: {
    width: 40,
    alignItems: 'flex-end',
    padding: 4,
  },
});
