// MenuElf Minimalist Light Theme

export const colors = {
  background: '#FFFFFF',
  backgroundSecondary: '#F7F7F7',
  backgroundTertiary: '#F0F0F0',
  border: '#E5E5E5',
  borderFocus: '#333333',
  accent: '#E85D3A',
  accentLight: '#FFF0EC',
  accentDark: '#C94E30',
  textPrimary: '#1A1A1A',
  textSecondary: '#6B6B6B',
  textTertiary: '#999999',
  matchHigh: '#E85D3A',
  matchMedium: '#6B6B6B',
  matchLow: '#CCCCCC',
  success: '#34A853',
  error: '#EA4335',
  star: '#F4B400',
  tabActive: '#1A1A1A',
  tabInactive: '#CCCCCC',
} as const;

export const typography = {
  hero: { fontSize: 32, fontWeight: 'bold' as const, color: colors.textPrimary },
  headingLarge: { fontSize: 24, fontWeight: 'bold' as const, color: colors.textPrimary },
  headingMedium: { fontSize: 20, fontWeight: '600' as const, color: colors.textPrimary },
  headingSmall: { fontSize: 17, fontWeight: '600' as const, color: colors.textPrimary },
  body: { fontSize: 15, fontWeight: 'normal' as const, color: colors.textPrimary },
  bodySecondary: { fontSize: 14, fontWeight: 'normal' as const, color: colors.textSecondary },
  caption: { fontSize: 12, fontWeight: 'normal' as const, color: colors.textTertiary },
  label: { fontSize: 11, fontWeight: '600' as const, color: colors.textSecondary, textTransform: 'uppercase' as const, letterSpacing: 1 },
  button: { fontSize: 15, fontWeight: '600' as const, color: '#FFFFFF' },
  price: { fontSize: 15, fontWeight: '600' as const, color: colors.accent },
  matchScore: { fontSize: 14, fontWeight: 'bold' as const, color: colors.accent },
} as const;

export const spacing = {
  screenPadding: 20,
  cardPadding: 16,
  cardGap: 12,
  sectionGap: 32,
} as const;

export const radii = {
  card: 16,
  button: 12,
  input: 8,
  pill: 24,
} as const;

export const shadows = {
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
  },
  elevated: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 6,
  },
} as const;

export function getMatchColor(score: number): string {
  if (score >= 80) return colors.matchHigh;
  if (score >= 50) return colors.matchMedium;
  return colors.matchLow;
}
