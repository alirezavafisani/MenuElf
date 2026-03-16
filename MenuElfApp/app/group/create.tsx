import React, { useState, useEffect } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity,
  FlatList, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiGet, apiPost } from '../../lib/api';
import { colors, radii, spacing } from '../../lib/theme';
import GoldButton from '../../components/ui/GoldButton';

type Friend = {
  id: string;
  username: string;
  display_name: string;
  avatar_emoji: string;
};

export default function CreatePlanScreen() {
  const router = useRouter();
  const [planName, setPlanName] = useState(
    `Dinner on ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
  );
  const [friends, setFriends] = useState<Friend[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadFriends();
  }, []);

  const loadFriends = async () => {
    setLoading(true);
    try {
      const res = await apiGet('/friends');
      if (res.ok) {
        const data = await res.json();
        setFriends(data.friends ?? []);
      }
    } catch {
      setError('Could not load friends');
    } finally {
      setLoading(false);
    }
  };

  const toggleFriend = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCreate = async () => {
    if (!planName.trim()) {
      Alert.alert('Name required', 'Please enter a name for the plan.');
      return;
    }
    if (selectedIds.size === 0) {
      Alert.alert('Select friends', 'Select at least one friend to invite.');
      return;
    }

    setCreating(true);
    try {
      const res = await apiPost('/plans', {
        name: planName.trim(),
        friend_ids: Array.from(selectedIds),
      });
      if (res.ok) {
        const data = await res.json();
        const planId = data.plan?.id;
        if (planId) {
          router.replace(`/group/${planId}`);
        } else {
          router.back();
        }
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed to create plan' }));
        Alert.alert('Error', err.detail ?? 'Something went wrong');
      }
    } catch {
      Alert.alert('Network error', 'Check your connection and try again.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Plan a Meal</Text>
        <View style={{ width: 44 }} />
      </View>

      <View style={styles.content}>
        {/* Plan name */}
        <Text style={styles.sectionLabel}>PLAN NAME</Text>
        <TextInput
          style={styles.nameInput}
          value={planName}
          onChangeText={setPlanName}
          placeholder="e.g. Friday dinner"
          placeholderTextColor={colors.textTertiary}
          maxLength={100}
        />

        {/* Friends selection */}
        <Text style={styles.sectionLabel}>SELECT FRIENDS</Text>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color={colors.goldPrimary} />
          </View>
        ) : friends.length === 0 ? (
          <View style={styles.center}>
            <Text style={styles.emptyText}>No friends yet. Add friends first!</Text>
          </View>
        ) : (
          <FlatList
            data={friends}
            keyExtractor={item => item.id}
            style={styles.list}
            renderItem={({ item }) => {
              const selected = selectedIds.has(item.id);
              return (
                <TouchableOpacity
                  style={[styles.friendRow, selected && styles.friendRowSelected]}
                  onPress={() => toggleFriend(item.id)}
                  activeOpacity={0.7}
                >
                  <Text style={styles.avatar}>{item.avatar_emoji ?? '🧝'}</Text>
                  <View style={styles.friendInfo}>
                    <Text style={styles.friendName}>{item.display_name ?? item.username}</Text>
                    <Text style={styles.friendUsername}>@{item.username}</Text>
                  </View>
                  <View style={[styles.checkbox, selected && styles.checkboxChecked]}>
                    {selected && <Ionicons name="checkmark" size={16} color="#FFFFFF" />}
                  </View>
                </TouchableOpacity>
              );
            }}
          />
        )}
      </View>

      {/* Create button */}
      <View style={styles.footer}>
        <Text style={styles.selectedCount}>
          {selectedIds.size} friend{selectedIds.size !== 1 ? 's' : ''} selected
        </Text>
        <GoldButton
          title="Create Plan"
          onPress={handleCreate}
          loading={creating}
          disabled={selectedIds.size === 0}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.screenPadding,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: { width: 44, padding: 8 },
  headerTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  content: {
    flex: 1,
    padding: spacing.screenPadding,
  },
  sectionLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.goldPrimary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 10,
    marginTop: 8,
  },
  nameInput: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.input,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: colors.textPrimary,
    marginBottom: 20,
  },
  list: { flex: 1 },
  friendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    marginBottom: 8,
  },
  friendRowSelected: {
    borderColor: colors.goldPrimary,
    backgroundColor: 'rgba(212,165,116,0.08)',
  },
  avatar: { fontSize: 32, marginRight: 12 },
  friendInfo: { flex: 1 },
  friendName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  friendUsername: { fontSize: 13, color: colors.textTertiary, marginTop: 1 },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkboxChecked: {
    backgroundColor: colors.goldDark,
    borderColor: colors.goldDark,
  },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyText: { fontSize: 15, color: colors.textSecondary },
  errorText: { color: colors.error, fontSize: 14, marginBottom: 8 },
  footer: {
    padding: spacing.screenPadding,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  selectedCount: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 10,
  },
});
