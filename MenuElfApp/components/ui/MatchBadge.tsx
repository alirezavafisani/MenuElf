import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { getMatchColor, colors, radii } from '../../lib/theme';

type Props = {
  score: number;
};

export default function MatchBadge({ score }: Props) {
  const color = getMatchColor(score);
  const isTopPick = score >= 90;

  return (
    <View style={[styles.badge, { borderColor: color }]}>
      {isTopPick && <Text style={[styles.topPick, { color }]}>Top Pick </Text>}
      <Text style={[styles.score, { color }]}>{score}% match</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
    backgroundColor: 'rgba(212,165,116,0.1)',
  },
  score: {
    fontSize: 12,
    fontWeight: '700',
  },
  topPick: {
    fontSize: 10,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
});
