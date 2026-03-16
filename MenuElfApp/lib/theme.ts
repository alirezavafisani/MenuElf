// MenuElf Dark Luxury Theme

export const colors = {
  background: '#0D0D0D',
  surface: '#1A1A1A',
  surfaceElevated: '#242424',
  border: '#2A2A2A',
  goldPrimary: '#D4A574',
  goldLight: '#E8C9A0',
  goldDark: '#B8894A',
  textPrimary: '#FFFFFF',
  textSecondary: '#A0A0A0',
  textTertiary: '#666666',
  success: '#4CAF50',
  error: '#FF5252',
  matchHigh: '#D4A574',
  matchMedium: '#A0A0A0',
  matchLow: '#666666',
  userBubble: '#2A2315',
} as const;

export const typography = {
  headingLarge: { fontSize: 28, fontWeight: 'bold' as const, color: colors.textPrimary },
  headingMedium: { fontSize: 22, fontWeight: 'bold' as const, color: colors.textPrimary },
  headingSmall: { fontSize: 18, fontWeight: '600' as const, color: colors.textPrimary },
  body: { fontSize: 15, fontWeight: 'normal' as const, color: colors.textPrimary },
  bodySecondary: { fontSize: 14, fontWeight: 'normal' as const, color: colors.textSecondary },
  caption: { fontSize: 12, fontWeight: 'normal' as const, color: colors.textTertiary },
  label: { fontSize: 13, fontWeight: '600' as const, color: colors.goldPrimary, textTransform: 'uppercase' as const },
  matchScore: { fontSize: 16, fontWeight: 'bold' as const, color: colors.goldPrimary },
  price: { fontSize: 15, fontWeight: '600' as const, color: colors.goldPrimary },
} as const;

export const spacing = {
  screenPadding: 20,
  cardPadding: 16,
  cardGap: 12,
  sectionGap: 24,
} as const;

export const radii = {
  card: 12,
  input: 8,
  pill: 24,
} as const;

export function getMatchColor(score: number): string {
  if (score >= 80) return colors.matchHigh;
  if (score >= 50) return colors.matchMedium;
  return colors.matchLow;
}

export const darkMapStyle = [
  { elementType: 'geometry', stylers: [{ color: '#212121' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#757575' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#212121' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#383838' }] },
  { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#9e9e9e' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#000000' }] },
  { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#181818' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#2f2f2f' }] },
];
