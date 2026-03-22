import React from 'react';
import { StyleSheet, View, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radii, spacing } from '../../lib/theme';
import AccentButton from '../../components/ui/AccentButton';
import { logInteraction } from '../../lib/api';

export default function IAteThisScreen() {
  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <View style={styles.content}>
        <Text style={styles.illustration}>&#127860;&#128247;</Text>
        <Text style={styles.heading}>I Ate This</Text>
        <Text style={styles.body}>
          Rate dishes and share your food journey with friends
        </Text>
        <Text style={styles.comingSoon}>Coming Soon</Text>
        <View style={styles.buttonContainer}>
          <AccentButton
            title="Get Notified"
            onPress={() => {
              logInteraction('iatethis_notify', {});
            }}
            inline
          />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.screenPadding,
  },
  illustration: {
    fontSize: 64,
    marginBottom: 24,
  },
  heading: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 12,
  },
  body: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 8,
    maxWidth: 280,
  },
  comingSoon: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textTertiary,
    marginBottom: 24,
  },
  buttonContainer: {
    width: 180,
  },
});
