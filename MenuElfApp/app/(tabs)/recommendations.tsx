import React, { useState, useEffect } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity,
  ActivityIndicator, ScrollView, Keyboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { apiGet, apiPost, logInteraction } from '../../lib/api';
import { colors, radii, spacing } from '../../lib/theme';
import SearchBar from '../../components/ui/SearchBar';
import DishCard from '../../components/ui/DishCard';
import GoldButton from '../../components/ui/GoldButton';

type Dish = {
  id: string;
  name: string;
  price: number | null;
  description: string;
  category: string;
  restaurant_slug: string;
  restaurant_name: string;
  dietary_info: string[];
};

export default function RecommendationsScreen() {
  const router = useRouter();

  const [query, setQuery] = useState('');
  const [priceMin, setPriceMin] = useState('');
  const [priceMax, setPriceMax] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedDietary, setSelectedDietary] = useState<string[]>([]);

  const [availableCategories, setAvailableCategories] = useState<string[]>([
    "Food", "Drink", "Side", "Dessert", "Appetizer", "Pizza", "Salad", "Pasta", "Soup", "Bread",
  ]);
  const [availableDietary, setAvailableDietary] = useState<string[]>([
    "vegan", "vegetarian", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "spicy",
  ]);
  const [results, setResults] = useState<Dish[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    apiGet('/filter-options')
      .then(res => res.json())
      .then(data => {
        if (data.categories) setAvailableCategories(data.categories);
        if (data.dietary_tags) setAvailableDietary(data.dietary_tags);
      })
      .catch(err => console.error("Could not load filter options:", err));
  }, []);

  const toggleCategory = (cat: string) => {
    setSelectedCategories(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  };

  const toggleDietary = (tag: string) => {
    const newTags = selectedDietary.includes(tag)
      ? selectedDietary.filter(t => t !== tag)
      : [...selectedDietary, tag];
    setSelectedDietary(newTags);
    logInteraction('filter_apply', { filter_type: 'dietary', value: tag });
  };

  const performSearch = async () => {
    setResults([]);
    setErrorMsg('');
    setLoading(true);
    setSearched(true);
    Keyboard.dismiss();

    try {
      const payload: any = {};
      if (query.trim()) payload.query = query.trim();
      if (priceMin.trim()) payload.price_min = parseFloat(priceMin);
      if (priceMax.trim()) payload.price_max = parseFloat(priceMax);
      if (selectedCategories.length > 0) payload.categories = selectedCategories;
      if (selectedDietary.length > 0) payload.dietary = selectedDietary;

      const res = await apiPost('/search-dishes', payload);
      const data = await res.json();
      const dishes = data.dishes || [];
      setResults(dishes);

      logInteraction('search_query', {
        query: query.trim(),
        results_count: dishes.length,
        filters: {
          price_min: priceMin || null,
          price_max: priceMax || null,
          categories: selectedCategories,
          dietary: selectedDietary,
        },
      });
    } catch (error) {
      console.error("Search failed:", error);
      setResults([]);
      setErrorMsg('Search failed. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const onDishPress = (item: Dish) => {
    logInteraction('dish_save', {
      dish_name: item.name,
      restaurant_slug: item.restaurant_slug,
      price: item.price,
      category: item.category,
    });
    router.push({ pathname: '/chat', params: { restaurant: item.restaurant_slug, dish: item.name } });
  };

  const renderChips = (
    items: string[],
    selected: string[],
    onToggle: (item: string) => void,
    capitalize?: boolean,
  ) => {
    const sorted = [...items].sort((a, b) => {
      const aS = selected.includes(a) ? 0 : 1;
      const bS = selected.includes(b) ? 0 : 1;
      return aS - bS;
    });
    return (
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll}>
        {sorted.map(item => {
          const active = selected.includes(item);
          return (
            <TouchableOpacity
              key={item}
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => onToggle(item)}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {capitalize ? item.toUpperCase() : item}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    );
  };

  const renderSkeleton = () => (
    <View style={styles.resultsPadding}>
      {[1, 2, 3].map(i => (
        <View key={i} style={styles.skeletonCard}>
          <View style={styles.skeletonTitle} />
          <View style={styles.skeletonSubtitle} />
          <View style={styles.skeletonLine} />
        </View>
      ))}
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.listContent} keyboardShouldPersistTaps="handled">
        <View style={styles.headerSection}>
          <Text style={styles.pageTitle}>Discover Dishes</Text>
          <Text style={styles.pageSubtitle}>Find exactly what you're craving</Text>

          <SearchBar
            value={query}
            onChangeText={setQuery}
            placeholder="e.g. warm creamy pasta without mushrooms"
            onSubmitEditing={performSearch}
          />

          <Text style={styles.sectionLabel}>PRICE RANGE</Text>
          <View style={styles.priceRow}>
            <TextInput
              style={styles.priceInput}
              placeholder="Min $"
              placeholderTextColor={colors.textTertiary}
              keyboardType="numeric"
              value={priceMin}
              onChangeText={setPriceMin}
            />
            <Text style={styles.priceDash}>-</Text>
            <TextInput
              style={styles.priceInput}
              placeholder="Max $"
              placeholderTextColor={colors.textTertiary}
              keyboardType="numeric"
              value={priceMax}
              onChangeText={setPriceMax}
            />
          </View>

          <Text style={styles.sectionLabel}>CATEGORIES</Text>
          {renderChips(availableCategories, selectedCategories, toggleCategory)}

          <Text style={styles.sectionLabel}>DIETARY NEEDS</Text>
          {renderChips(availableDietary, selectedDietary, toggleDietary, true)}

          <GoldButton title="Find Dishes" onPress={performSearch} />
        </View>

        {loading && renderSkeleton()}

        {!loading && errorMsg ? (
          <Text style={styles.errorText}>{errorMsg}</Text>
        ) : null}

        {!loading && searched && !errorMsg && results.length === 0 && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No dishes found</Text>
            <Text style={styles.emptySubtext}>Try loosening your filters</Text>
          </View>
        )}

        {results.length > 0 && (
          <View style={styles.resultsPadding}>
            {results.map((item, idx) => (
              <DishCard
                key={`${item.id}-${idx}`}
                name={item.name}
                price={item.price}
                description={item.description}
                restaurantName={item.restaurant_name}
                category={item.category}
                dietaryTags={item.dietary_info}
                onPress={() => onDishPress(item)}
              />
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  listContent: { paddingBottom: 40 },
  headerSection: {
    padding: spacing.screenPadding,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    marginBottom: spacing.cardGap,
  },
  pageTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  pageSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 20,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 10,
    marginTop: 20,
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  priceInput: {
    backgroundColor: colors.backgroundTertiary,
    borderRadius: radii.input,
    paddingHorizontal: 15,
    height: 44,
    width: 100,
    fontSize: 16,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  priceDash: {
    fontSize: 18,
    color: colors.textTertiary,
    marginHorizontal: 15,
  },
  chipScroll: {
    marginBottom: 16,
  },
  chip: {
    backgroundColor: colors.backgroundSecondary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: radii.pill,
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.accentLight,
    borderColor: colors.accent,
  },
  chipText: {
    color: colors.textSecondary,
    fontWeight: '600',
    fontSize: 12,
  },
  chipTextActive: {
    color: colors.accent,
  },
  resultsPadding: {
    paddingHorizontal: spacing.screenPadding,
  },
  errorText: {
    textAlign: 'center',
    color: colors.error,
    marginTop: 20,
    fontSize: 16,
    fontWeight: '600',
    paddingHorizontal: spacing.screenPadding,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 4,
  },
  emptySubtext: {
    fontSize: 14,
    color: colors.textTertiary,
  },
  skeletonCard: {
    backgroundColor: colors.backgroundSecondary,
    borderRadius: radii.card,
    padding: spacing.cardPadding,
    marginBottom: spacing.cardGap,
  },
  skeletonTitle: {
    width: '60%',
    height: 16,
    backgroundColor: colors.backgroundTertiary,
    borderRadius: 4,
    marginBottom: 10,
  },
  skeletonSubtitle: {
    width: '40%',
    height: 12,
    backgroundColor: colors.backgroundTertiary,
    borderRadius: 4,
    marginBottom: 10,
  },
  skeletonLine: {
    width: '80%',
    height: 12,
    backgroundColor: colors.backgroundTertiary,
    borderRadius: 4,
  },
});
