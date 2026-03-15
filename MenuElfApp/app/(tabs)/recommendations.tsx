import React, { useState, useEffect } from 'react';
import {
    StyleSheet, View, Text, TextInput, TouchableOpacity,
    ActivityIndicator, ScrollView, Keyboard
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiGet, apiPost, logInteraction } from '../../lib/api';

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

    // Filter State
    const [query, setQuery] = useState('');
    const [priceMin, setPriceMin] = useState('');
    const [priceMax, setPriceMax] = useState('');
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [selectedDietary, setSelectedDietary] = useState<string[]>([]);

    // Data State
    const [availableCategories, setAvailableCategories] = useState<string[]>([
        "Food", "Drink", "Side", "Dessert", "Appetizer", "Pizza", "Salad", "Pasta", "Soup", "Bread"
    ]);
    const [availableDietary, setAvailableDietary] = useState<string[]>([
        "vegan", "vegetarian", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "spicy"
    ]);
    const [results, setResults] = useState<Dish[]>([]);
    const [loading, setLoading] = useState(false);
    const [searched, setSearched] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');

    useEffect(() => {
        // Fetch available filter options from the backend
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

        // Log filter application
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

            // Log the search query
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
        // Log dish save interaction
        logInteraction('dish_save', {
            dish_name: item.name,
            restaurant_slug: item.restaurant_slug,
            price: item.price,
            category: item.category,
        });

        router.push({ pathname: '/chat', params: { restaurant: item.restaurant_slug, dish: item.name } });
    };

    const renderHeader = () => (
        <View style={styles.headerContainer}>
            <Text style={styles.pageTitle}>Dish Recommender</Text>
            <Text style={styles.pageSubtitle}>Find exactly what you&apos;re craving</Text>

            <View style={styles.searchBox}>
                <Ionicons name="search" size={20} color="#999" style={styles.searchIcon} />
                <TextInput
                    style={styles.searchInput}
                    placeholder="e.g. warm creamy pasta without mushrooms"
                    placeholderTextColor="#999"
                    value={query}
                    onChangeText={setQuery}
                    onSubmitEditing={performSearch}
                    returnKeyType="search"
                />
            </View>

            <Text style={styles.sectionTitle}>Price Range</Text>
            <View style={styles.priceRow}>
                <TextInput
                    style={styles.priceInput}
                    placeholder="Min $"
                    placeholderTextColor="#999"
                    keyboardType="numeric"
                    value={priceMin}
                    onChangeText={setPriceMin}
                />
                <Text style={styles.priceDash}>-</Text>
                <TextInput
                    style={styles.priceInput}
                    placeholder="Max $"
                    placeholderTextColor="#999"
                    keyboardType="numeric"
                    value={priceMax}
                    onChangeText={setPriceMax}
                />
            </View>

            <Text style={styles.sectionTitle}>Categories</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipContainer}>
                {[...availableCategories].sort((a, b) => {
                    const aSelected = selectedCategories.includes(a) ? 0 : 1;
                    const bSelected = selectedCategories.includes(b) ? 0 : 1;
                    return aSelected - bSelected;
                }).map(cat => {
                    const active = selectedCategories.includes(cat);
                    return (
                        <TouchableOpacity
                            key={cat}
                            style={[styles.chip, active && styles.chipActive]}
                            onPress={() => toggleCategory(cat)}
                        >
                            <Text style={[styles.chipText, active && styles.chipTextActive]}>{cat}</Text>
                        </TouchableOpacity>
                    );
                })}
            </ScrollView>

            <Text style={styles.sectionTitle}>Dietary Needs</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipContainer}>
                {[...availableDietary].sort((a, b) => {
                    const aSelected = selectedDietary.includes(a) ? 0 : 1;
                    const bSelected = selectedDietary.includes(b) ? 0 : 1;
                    return aSelected - bSelected;
                }).map(tag => {
                    const active = selectedDietary.includes(tag);
                    return (
                        <TouchableOpacity
                            key={tag}
                            style={[styles.chip, active && styles.chipActive]}
                            onPress={() => toggleDietary(tag)}
                        >
                            <Text style={[styles.chipText, active && styles.chipTextActive]}>{tag.toUpperCase()}</Text>
                        </TouchableOpacity>
                    );
                })}
            </ScrollView>

            <TouchableOpacity style={styles.searchBtn} onPress={performSearch}>
                <Text style={styles.searchBtnText}>Find Dishes</Text>
            </TouchableOpacity>

            {loading && <ActivityIndicator size="large" color="#FF6B6B" style={styles.loader} />}

            {!loading && errorMsg ? (
                <Text style={styles.errorText}>{errorMsg}</Text>
            ) : null}

            {!loading && searched && !errorMsg && results.length === 0 && (
                <Text style={styles.noResults}>No dishes found. Try loosening your filters!</Text>
            )}
        </View>
    );

    const renderDishCard = (item: Dish, idx: number) => (
        <TouchableOpacity
            key={`${item.id}-${idx}`}
            style={styles.card}
            activeOpacity={0.7}
            onPress={() => onDishPress(item)}
        >
            <View style={styles.cardHeader}>
                <Text style={styles.dishName} numberOfLines={1}>{item.name}</Text>
                <Text style={styles.dishPrice}>{item.price != null ? `$${item.price.toFixed(2)}` : 'Pricing N/A'}</Text>
            </View>
            <Text style={styles.restaurantName}>
                <Ionicons name="restaurant-outline" size={14} color="#FF6B6B" /> {item.restaurant_name}
            </Text>
            {(item.description && item.description.trim() !== "") && (
                <Text style={styles.dishDesc} numberOfLines={2}>{item.description}</Text>
            )}

            <View style={styles.tagsRow}>
                <View style={styles.categoryBadge}>
                    <Text style={styles.categoryBadgeText}>{item.category || 'FOOD'}</Text>
                </View>
                {Array.isArray(item.dietary_info) && item.dietary_info.map((tag, idx) => (
                    <View key={idx} style={styles.dietaryBadge}>
                        <Text style={styles.dietaryBadgeText}>{tag}</Text>
                    </View>
                ))}
            </View>
        </TouchableOpacity>
    );

    return (
        <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
            <ScrollView contentContainerStyle={styles.listContent} keyboardShouldPersistTaps="handled">
                {renderHeader()}
                {results.map((item, idx) => renderDishCard(item, idx))}
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F9F9FB',
    },
    listContent: {
        paddingBottom: 40,
    },
    headerContainer: {
        padding: 20,
        backgroundColor: '#FFFFFF',
        borderBottomWidth: 1,
        borderBottomColor: '#F0F0F0',
        marginBottom: 10,
    },
    pageTitle: {
        fontSize: 28,
        fontWeight: '800',
        color: '#1A1A1A',
        marginBottom: 4,
    },
    pageSubtitle: {
        fontSize: 16,
        color: '#7A7A7A',
        marginBottom: 20,
    },
    searchBox: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#F5F5F5',
        borderRadius: 12,
        paddingHorizontal: 15,
        height: 50,
        marginBottom: 20,
    },
    searchIcon: {
        marginRight: 10,
    },
    searchInput: {
        flex: 1,
        fontSize: 16,
        color: '#333',
    },
    sectionTitle: {
        fontSize: 16,
        fontWeight: '700',
        color: '#333',
        marginBottom: 10,
        marginTop: 5,
    },
    priceRow: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 20,
    },
    priceInput: {
        backgroundColor: '#F5F5F5',
        borderRadius: 8,
        paddingHorizontal: 15,
        height: 44,
        width: 100,
        fontSize: 16,
        textAlign: 'center',
    },
    priceDash: {
        fontSize: 18,
        color: '#999',
        marginHorizontal: 15,
    },
    chipContainer: {
        flexDirection: 'row',
        marginBottom: 20,
    },
    chip: {
        backgroundColor: '#F5F5F5',
        paddingHorizontal: 16,
        paddingVertical: 10,
        borderRadius: 20,
        marginRight: 10,
        borderWidth: 1,
        borderColor: '#EEE',
    },
    chipActive: {
        backgroundColor: '#FF6B6B',
        borderColor: '#FF6B6B',
    },
    chipText: {
        color: '#555',
        fontWeight: '600',
    },
    chipTextActive: {
        color: '#FFF',
    },
    searchBtn: {
        backgroundColor: '#1A1A1A',
        borderRadius: 12,
        height: 54,
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 10,
        marginBottom: 10,
    },
    searchBtnText: {
        color: '#FFF',
        fontSize: 18,
        fontWeight: '700',
    },
    loader: {
        marginTop: 20,
    },
    noResults: {
        textAlign: 'center',
        color: '#999',
        marginTop: 20,
        fontSize: 16,
    },
    errorText: {
        textAlign: 'center',
        color: '#E74C3C',
        marginTop: 20,
        fontSize: 16,
        fontWeight: '600',
    },
    card: {
        backgroundColor: '#FFF',
        marginHorizontal: 20,
        marginBottom: 15,
        borderRadius: 16,
        padding: 16,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.05,
        shadowRadius: 10,
        elevation: 2,
        borderWidth: 1,
        borderColor: '#F0F0F0',
    },
    cardHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 6,
    },
    dishName: {
        flex: 1,
        fontSize: 18,
        fontWeight: '700',
        color: '#1A1A1A',
        marginRight: 10,
    },
    dishPrice: {
        fontSize: 16,
        fontWeight: '800',
        color: '#27AE60',
    },
    restaurantName: {
        fontSize: 14,
        color: '#FF6B6B',
        fontWeight: '600',
        marginBottom: 8,
    },
    dishDesc: {
        fontSize: 14,
        color: '#666',
        lineHeight: 20,
        marginBottom: 12,
    },
    tagsRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 8,
    },
    categoryBadge: {
        backgroundColor: '#F5F5F5',
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 6,
    },
    categoryBadgeText: {
        fontSize: 10,
        fontWeight: '700',
        color: '#666',
        textTransform: 'uppercase',
    },
    dietaryBadge: {
        backgroundColor: '#E8F5E9',
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 6,
    },
    dietaryBadgeText: {
        fontSize: 10,
        fontWeight: '700',
        color: '#2E7D32',
        textTransform: 'uppercase',
    },
});
