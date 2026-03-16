import React from 'react';
import { StyleSheet, View, Text, TouchableOpacity, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import { logInteraction } from '../../lib/api';
import { colors, radii, spacing } from '../../lib/theme';
import GoldButton from '../../components/ui/GoldButton';

export default function FriendsScreen() {
  const handleLogout = () => {
    Alert.alert('Log Out', 'Are you sure you want to log out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Log Out',
        style: 'destructive',
        onPress: () => supabase.auth.signOut(),
      },
    ]);
  };

  const handleNotify = () => {
    logInteraction('notify_request', { feature: 'social_dining' });
    Alert.alert('Got it!', "We'll let you know when Social Dining launches.");
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <View style={styles.centerBox}>
        <Text style={styles.emojiComposition}>&#127869;&#129309;&#128101;</Text>
        <Text style={styles.heading}>Social Dining</Text>
        <Text style={styles.title}>Group dining is coming soon</Text>
        <Text style={styles.subtitle}>
          Find restaurants everyone loves, powered by AI
        </Text>
        <View style={styles.buttonContainer}>
          <GoldButton title="Get Notified" onPress={handleNotify} />
        </View>
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Log Out</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centerBox: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
    backgroundColor: colors.surface,
    margin: spacing.screenPadding,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  emojiComposition: {
    fontSize: 56,
    marginBottom: 24,
  },
  heading: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.goldPrimary,
    textTransform: 'uppercase',
    letterSpacing: 2,
    marginBottom: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.textPrimary,
    marginBottom: 12,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  buttonContainer: {
    width: '100%',
    maxWidth: 240,
  },
  logoutBtn: {
    marginHorizontal: spacing.screenPadding,
    marginBottom: spacing.screenPadding,
    paddingVertical: 14,
    borderRadius: radii.input,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
  },
  logoutText: {
    color: colors.error,
    fontSize: 16,
    fontWeight: '600',
  },
});
