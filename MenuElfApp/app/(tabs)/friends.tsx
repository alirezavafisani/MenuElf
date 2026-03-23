import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  StyleSheet, View, Text, TouchableOpacity, FlatList,
  TextInput, Alert, RefreshControl, ActivityIndicator,
  Animated, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { supabase } from '../../lib/supabase';
import { apiGet, apiPost, apiDelete, logInteraction } from '../../lib/api';
import { colors, radii, spacing, shadows } from '../../lib/theme';
import GoldButton from '../../components/ui/GoldButton';
import SearchBar from '../../components/ui/SearchBar';

// ── Types ──

type UserProfile = {
  id: string;
  username: string;
  display_name: string;
  avatar_emoji: string;
  taste_summary?: {
    top_cuisines?: string[];
    dietary_restrictions?: string[];
  };
};

type FriendRequest = {
  id: string;
  from_user_id: string;
  to_user_id: string;
  status: string;
  from_profile?: { username: string; display_name: string; avatar_emoji: string };
  to_profile?: { username: string; display_name: string; avatar_emoji: string };
};

type SearchUser = {
  id: string;
  username: string;
  display_name: string;
  avatar_emoji: string;
};

type DiningPlan = {
  id: string;
  name: string;
  status: string;
  members?: {
    user_id: string;
    status: string;
    profile?: { avatar_emoji: string };
  }[];
  my_status?: string;
};

// ── Avatar Emoji Choices ──

const AVATAR_EMOJIS = [
  '\u{1F9DD}', '\u{1F9D1}\u200D\u{1F373}', '\u{1F355}', '\u{1F363}', '\u{1F32E}', '\u{1F35C}',
  '\u{1F957}', '\u{1F370}', '\u{1F354}', '\u{1F958}', '\u{1F9C1}', '\u{1F377}',
];

// ── Tabs ──

type TabName = 'friends' | 'requests' | 'add';

// ── Main Component ──

export default function FriendsScreen() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabName>('friends');
  const [myProfile, setMyProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState('');

  const [plans, setPlans] = useState<DiningPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(false);

  const [friends, setFriends] = useState<UserProfile[]>([]);
  const [friendsLoading, setFriendsLoading] = useState(false);
  const [friendsRefreshing, setFriendsRefreshing] = useState(false);

  const [incoming, setIncoming] = useState<FriendRequest[]>([]);
  const [outgoing, setOutgoing] = useState<FriendRequest[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [requestsRefreshing, setRequestsRefreshing] = useState(false);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [decliningId, setDecliningId] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchUser[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [sentRequestUsernames, setSentRequestUsernames] = useState<Set<string>>(new Set());

  const [setupUsername, setSetupUsername] = useState('');
  const [setupDisplayName, setSetupDisplayName] = useState('');
  const [setupEmoji, setSetupEmoji] = useState(AVATAR_EMOJIS[0]);
  const [setupLoading, setSetupLoading] = useState(false);
  const [setupError, setSetupError] = useState('');

  useEffect(() => { loadMyProfile(); }, []);

  useEffect(() => {
    if (myProfile) {
      if (activeTab === 'friends') { loadFriends(); loadPlans(); }
      if (activeTab === 'requests') loadRequests();
    }
  }, [activeTab, myProfile]);

  useEffect(() => {
    if (activeTab !== 'add' || !searchQuery.trim()) { setSearchResults([]); return; }
    const timer = setTimeout(() => searchUsers(searchQuery.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, activeTab]);

  const loadMyProfile = async () => {
    setProfileLoading(true);
    setProfileError('');
    try {
      const res = await apiGet('/profile/me');
      if (res.ok) { const data = await res.json(); setMyProfile(data.profile); }
      else if (res.status === 404) { setMyProfile(null); }
      else { setProfileError('Could not load profile'); }
    } catch { setProfileError('Network error. Check your connection.'); }
    finally { setProfileLoading(false); }
  };

  const loadPlans = async () => {
    setPlansLoading(true);
    try {
      const res = await apiGet('/plans');
      if (res.ok) { const data = await res.json(); setPlans(data.plans ?? []); }
    } catch {} finally { setPlansLoading(false); }
  };

  const loadFriends = async (refreshing = false) => {
    if (refreshing) setFriendsRefreshing(true); else setFriendsLoading(true);
    try {
      const res = await apiGet('/friends');
      if (res.ok) { const data = await res.json(); setFriends(data.friends ?? []); }
    } catch {} finally { setFriendsLoading(false); setFriendsRefreshing(false); }
  };

  const loadRequests = async (refreshing = false) => {
    if (refreshing) setRequestsRefreshing(true); else setRequestsLoading(true);
    try {
      const [inRes, outRes] = await Promise.all([
        apiGet('/friends/requests/incoming'),
        apiGet('/friends/requests/outgoing'),
      ]);
      if (inRes.ok) { const inData = await inRes.json(); setIncoming(inData.requests ?? []); }
      if (outRes.ok) { const outData = await outRes.json(); setOutgoing(outData.requests ?? []); }
    } catch {} finally { setRequestsLoading(false); setRequestsRefreshing(false); }
  };

  const searchUsers = async (q: string) => {
    setSearchLoading(true);
    try {
      const res = await apiGet(`/users/search?q=${encodeURIComponent(q)}`);
      if (res.ok) { const data = await res.json(); setSearchResults(data.users ?? []); }
    } catch { setSearchResults([]); } finally { setSearchLoading(false); }
  };

  const sendFriendRequest = async (username: string) => {
    try {
      const res = await apiPost('/friends/request', { username });
      if (res.ok) {
        setSentRequestUsernames(prev => new Set(prev).add(username));
        logInteraction('friend_request_sent', { target_username: username });
      } else {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        Alert.alert('Could not send request', err.detail ?? 'Something went wrong');
      }
    } catch { Alert.alert('Network error', 'Check your connection and try again.'); }
  };

  const acceptRequest = async (requestId: string) => {
    setAcceptingId(requestId);
    try {
      const res = await apiPost(`/friends/requests/${requestId}/accept`, {});
      if (res.ok) { setIncoming(prev => prev.filter(r => r.id !== requestId)); loadFriends(); }
      else { Alert.alert('Error', 'Could not accept request'); }
    } catch { Alert.alert('Network error', 'Check your connection.'); }
    finally { setAcceptingId(null); }
  };

  const declineRequest = async (requestId: string) => {
    setDecliningId(requestId);
    try {
      const res = await apiPost(`/friends/requests/${requestId}/decline`, {});
      if (res.ok) { setIncoming(prev => prev.filter(r => r.id !== requestId)); }
      else { Alert.alert('Error', 'Could not decline request'); }
    } catch { Alert.alert('Network error', 'Check your connection.'); }
    finally { setDecliningId(null); }
  };

  const removeFriend = (friendId: string, friendName: string) => {
    Alert.alert('Remove Friend', `Remove ${friendName} from your friends?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove', style: 'destructive',
        onPress: async () => {
          try {
            const res = await apiDelete(`/friends/${friendId}`);
            if (res.ok) { setFriends(prev => prev.filter(f => f.id !== friendId)); }
            else { Alert.alert('Error', 'Could not remove friend'); }
          } catch { Alert.alert('Network error', 'Check your connection.'); }
        },
      },
    ]);
  };

  const handleLogout = () => {
    Alert.alert('Log Out', 'Are you sure you want to log out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Log Out', style: 'destructive', onPress: () => supabase.auth.signOut() },
    ]);
  };

  const [deletingAccount, setDeletingAccount] = useState(false);

  const handleDeleteAccount = () => {
    Alert.alert(
      'Delete Account',
      'This will permanently delete your account and all data. This cannot be undone. Are you sure?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Account',
          style: 'destructive',
          onPress: async () => {
            setDeletingAccount(true);
            try {
              const res = await apiDelete('/profile/account');
              if (res.ok) {
                await supabase.auth.signOut();
              } else {
                Alert.alert('Error', 'Could not delete account. Please try again.');
              }
            } catch {
              Alert.alert('Network error', 'Check your connection and try again.');
            } finally {
              setDeletingAccount(false);
            }
          },
        },
      ]
    );
  };

  const setupProfile = async () => {
    const username = setupUsername.trim().toLowerCase();
    if (!username) { setSetupError('Username is required'); return; }
    if (!/^[a-z0-9_]{3,20}$/.test(username)) {
      setSetupError('3-20 characters, lowercase letters, numbers, and underscores only');
      return;
    }
    setSetupLoading(true);
    setSetupError('');
    try {
      const res = await apiPost('/profile/setup', {
        username,
        display_name: setupDisplayName.trim() || username,
        avatar_emoji: setupEmoji,
      });
      if (res.ok) {
        const data = await res.json();
        setMyProfile(data.profile);
        logInteraction('profile_created', { username });
      } else {
        const err = await res.json().catch(() => ({ detail: 'Setup failed' }));
        setSetupError(err.detail ?? 'Something went wrong');
      }
    } catch { setSetupError('Network error. Check your connection.'); }
    finally { setSetupLoading(false); }
  };

  // ── Render: Loading state ──
  if (profileLoading) {
    return (
      <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  // ── Render: Profile setup ──
  if (!myProfile) {
    return (
      <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
        <ScrollView contentContainerStyle={styles.setupContainer} keyboardShouldPersistTaps="handled">
          <Text style={styles.setupTitle}>Set Up Your Profile</Text>
          <Text style={styles.setupSubtitle}>Choose a username so friends can find you</Text>

          <Text style={styles.sectionLabel}>AVATAR</Text>
          <View style={styles.emojiGrid}>
            {AVATAR_EMOJIS.map(emoji => (
              <TouchableOpacity
                key={emoji}
                style={[styles.emojiOption, setupEmoji === emoji && styles.emojiSelected]}
                onPress={() => setSetupEmoji(emoji)}
              >
                <Text style={styles.emojiText}>{emoji}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.sectionLabel}>USERNAME</Text>
          <TextInput
            style={styles.setupInput}
            placeholder="e.g. foodie_jane"
            placeholderTextColor={colors.textTertiary}
            value={setupUsername}
            onChangeText={(t) => { setSetupUsername(t.toLowerCase().replace(/[^a-z0-9_]/g, '')); setSetupError(''); }}
            autoCapitalize="none"
            autoCorrect={false}
            maxLength={20}
          />
          <Text style={styles.setupHint}>3-20 chars, lowercase, numbers, underscores</Text>

          <Text style={styles.sectionLabel}>DISPLAY NAME</Text>
          <TextInput
            style={styles.setupInput}
            placeholder="Your name (optional)"
            placeholderTextColor={colors.textTertiary}
            value={setupDisplayName}
            onChangeText={setSetupDisplayName}
            maxLength={50}
          />

          {setupError ? <Text style={styles.errorText}>{setupError}</Text> : null}
          {profileError ? <Text style={styles.errorText}>{profileError}</Text> : null}

          <View style={styles.setupButtonRow}>
            <GoldButton title="Create Profile" onPress={setupProfile} loading={setupLoading} />
          </View>
        </ScrollView>

        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Text style={styles.logoutText}>Log Out</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  // ── Render: Main tabbed screen ──
  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <View style={styles.tabBar}>
        {(['friends', 'requests', 'add'] as TabName[]).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === 'friends' ? 'Friends' : tab === 'requests' ? 'Requests' : 'Add Friend'}
            </Text>
            {tab === 'requests' && incoming.length > 0 && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{incoming.length}</Text>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Tab: Friends ── */}
      {activeTab === 'friends' && (
        <>
          {friendsLoading && friends.length === 0 ? (
            <View style={styles.center}>
              <ActivityIndicator size="large" color={colors.accent} />
            </View>
          ) : (
            <FlatList
              data={friends}
              keyExtractor={item => item.id}
              contentContainerStyle={styles.listContent}
              refreshControl={
                <RefreshControl
                  refreshing={friendsRefreshing}
                  onRefresh={() => { loadFriends(true); loadPlans(); }}
                  tintColor={colors.accent}
                />
              }
              ListHeaderComponent={
                <View>
                  <Text style={styles.sectionLabel}>DINING PLANS</Text>
                  <View style={{ marginBottom: 8 }}>
                    <GoldButton title="+ New Plan" onPress={() => router.push('/group/create')} />
                  </View>
                  {plansLoading && plans.length === 0 ? (
                    <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 12 }} />
                  ) : plans.length > 0 ? (
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.plansScroll} contentContainerStyle={styles.plansScrollContent}>
                      {plans.map(plan => {
                        const avatars = (plan.members ?? [])
                          .filter(m => m.status === 'joined')
                          .map(m => m.profile?.avatar_emoji ?? '\u{1F9DD}')
                          .slice(0, 5);
                        const isInvited = plan.my_status === 'invited';
                        return (
                          <TouchableOpacity
                            key={plan.id}
                            style={[styles.planCard, isInvited && styles.planCardInvited]}
                            onPress={() => router.push(`/group/${plan.id}`)}
                            activeOpacity={0.7}
                          >
                            <Text style={styles.planName} numberOfLines={1}>{plan.name}</Text>
                            <Text style={styles.planAvatars}>{avatars.join(' ')}</Text>
                            <View style={[
                              styles.planStatusBadge,
                              plan.status === 'decided' && styles.planStatusDecided,
                              plan.status === 'cancelled' && styles.planStatusCancelled,
                              isInvited && styles.planStatusInvited,
                            ]}>
                              <Text style={styles.planStatusText}>
                                {isInvited ? 'Invited!' : plan.status === 'decided' ? 'Decided' : plan.status === 'cancelled' ? 'Cancelled' : 'Active'}
                              </Text>
                            </View>
                          </TouchableOpacity>
                        );
                      })}
                    </ScrollView>
                  ) : (
                    <Text style={styles.plansEmpty}>No plans yet — create one above!</Text>
                  )}

                  <Text style={[styles.sectionLabel, { marginTop: 20 }]}>FRIENDS</Text>
                  {friends.length === 0 && (
                    <View style={{ alignItems: 'center', paddingVertical: 24 }}>
                      <Text style={styles.emptyEmoji}>&#128101;</Text>
                      <Text style={styles.emptyTitle}>No friends yet</Text>
                      <Text style={styles.emptySubtext}>Add friends to plan meals together</Text>
                      <View style={{ marginTop: 16, width: 200 }}>
                        <GoldButton title="Add Friends" onPress={() => setActiveTab('add')} />
                      </View>
                    </View>
                  )}
                </View>
              }
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={styles.friendCard}
                  onLongPress={() => removeFriend(item.id, item.display_name ?? item.username)}
                  activeOpacity={0.8}
                >
                  <Text style={styles.avatar}>{item.avatar_emoji ?? '\u{1F9DD}'}</Text>
                  <View style={styles.friendInfo}>
                    <Text style={styles.friendName}>{item.display_name ?? item.username}</Text>
                    <Text style={styles.friendUsername}>@{item.username}</Text>
                    {item.taste_summary?.top_cuisines && item.taste_summary.top_cuisines.length > 0 && (
                      <Text style={styles.friendCuisines}>
                        Loves {item.taste_summary.top_cuisines.slice(0, 3).join(', ')}
                      </Text>
                    )}
                  </View>
                </TouchableOpacity>
              )}
            />
          )}

          <TouchableOpacity style={styles.fab} onPress={() => setActiveTab('add')} activeOpacity={0.8}>
            <Ionicons name="add" size={28} color="#FFFFFF" />
          </TouchableOpacity>
        </>
      )}

      {/* ── Tab: Requests ── */}
      {activeTab === 'requests' && (
        <ScrollView
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={requestsRefreshing} onRefresh={() => loadRequests(true)} tintColor={colors.accent} />
          }
        >
          {requestsLoading && incoming.length === 0 && outgoing.length === 0 ? (
            <View style={[styles.center, { paddingVertical: 60 }]}>
              <ActivityIndicator size="large" color={colors.accent} />
            </View>
          ) : (
            <>
              {incoming.length > 0 && (
                <>
                  <Text style={styles.sectionLabel}>INCOMING</Text>
                  {incoming.map(req => (
                    <View key={req.id} style={styles.requestCard}>
                      <Text style={styles.avatar}>{req.from_profile?.avatar_emoji ?? '\u{1F9DD}'}</Text>
                      <View style={styles.friendInfo}>
                        <Text style={styles.friendName}>{req.from_profile?.display_name ?? 'Unknown'}</Text>
                        <Text style={styles.friendUsername}>@{req.from_profile?.username ?? '...'}</Text>
                      </View>
                      <View style={styles.requestActions}>
                        <TouchableOpacity
                          style={styles.acceptBtn}
                          onPress={() => acceptRequest(req.id)}
                          disabled={acceptingId === req.id}
                        >
                          {acceptingId === req.id ? (
                            <ActivityIndicator size="small" color="#FFFFFF" />
                          ) : (
                            <Ionicons name="checkmark" size={18} color="#FFFFFF" />
                          )}
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={styles.declineBtn}
                          onPress={() => declineRequest(req.id)}
                          disabled={decliningId === req.id}
                        >
                          {decliningId === req.id ? (
                            <ActivityIndicator size="small" color={colors.textSecondary} />
                          ) : (
                            <Ionicons name="close" size={18} color={colors.textSecondary} />
                          )}
                        </TouchableOpacity>
                      </View>
                    </View>
                  ))}
                </>
              )}

              {outgoing.length > 0 && (
                <>
                  <Text style={[styles.sectionLabel, incoming.length > 0 && { marginTop: 24 }]}>SENT</Text>
                  {outgoing.map(req => (
                    <View key={req.id} style={styles.requestCard}>
                      <Text style={styles.avatar}>{req.to_profile?.avatar_emoji ?? '\u{1F9DD}'}</Text>
                      <View style={styles.friendInfo}>
                        <Text style={styles.friendName}>{req.to_profile?.display_name ?? 'Unknown'}</Text>
                        <Text style={styles.friendUsername}>@{req.to_profile?.username ?? '...'}</Text>
                      </View>
                      <View style={styles.pendingBadge}>
                        <Text style={styles.pendingText}>Pending</Text>
                      </View>
                    </View>
                  ))}
                </>
              )}

              {incoming.length === 0 && outgoing.length === 0 && (
                <View style={[styles.center, { paddingVertical: 60 }]}>
                  <Text style={styles.emptyTitle}>No pending requests</Text>
                  <Text style={styles.emptySubtext}>Friend requests will appear here</Text>
                </View>
              )}
            </>
          )}
        </ScrollView>
      )}

      {/* ── Tab: Add Friend ── */}
      {activeTab === 'add' && (
        <View style={styles.addContainer}>
          <View style={styles.searchPadding}>
            <SearchBar value={searchQuery} onChangeText={setSearchQuery} placeholder="Search by username..." />
          </View>

          {searchLoading ? (
            <View style={[styles.center, { paddingVertical: 40 }]}>
              <ActivityIndicator size="large" color={colors.accent} />
            </View>
          ) : searchQuery.trim().length === 0 ? (
            <View style={[styles.center, { paddingVertical: 40 }]}>
              <Text style={styles.emptySubtext}>Type a username to search</Text>
            </View>
          ) : searchResults.length === 0 ? (
            <View style={[styles.center, { paddingVertical: 40 }]}>
              <Text style={styles.emptyTitle}>No users found</Text>
              <Text style={styles.emptySubtext}>Try a different username</Text>
            </View>
          ) : (
            <FlatList
              data={searchResults}
              keyExtractor={item => item.id}
              contentContainerStyle={styles.listContent}
              keyboardShouldPersistTaps="handled"
              renderItem={({ item }) => {
                const alreadySent = sentRequestUsernames.has(item.username);
                return (
                  <View style={styles.searchResultCard}>
                    <Text style={styles.avatar}>{item.avatar_emoji ?? '\u{1F9DD}'}</Text>
                    <View style={styles.friendInfo}>
                      <Text style={styles.friendName}>{item.display_name ?? item.username}</Text>
                      <Text style={styles.friendUsername}>@{item.username}</Text>
                    </View>
                    <TouchableOpacity
                      style={[styles.addBtn, alreadySent && styles.addBtnDisabled]}
                      onPress={() => !alreadySent && sendFriendRequest(item.username)}
                      disabled={alreadySent}
                    >
                      <Text style={[styles.addBtnText, alreadySent && styles.addBtnTextDisabled]}>
                        {alreadySent ? 'Sent' : 'Add'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                );
              }}
            />
          )}
        </View>
      )}

      {activeTab === 'friends' && (
        <View style={styles.footerSection}>
          <View style={styles.legalLinks}>
            <TouchableOpacity onPress={() => router.push('/legal?type=privacy')}>
              <Text style={styles.legalText}>Privacy Policy</Text>
            </TouchableOpacity>
            <Text style={styles.legalDot}> · </Text>
            <TouchableOpacity onPress={() => router.push('/legal?type=terms')}>
              <Text style={styles.legalText}>Terms</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
            <Text style={styles.logoutText}>Log Out</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.deleteAccountBtn}
            onPress={handleDeleteAccount}
            disabled={deletingAccount}
          >
            {deletingAccount ? (
              <ActivityIndicator size="small" color={colors.error} />
            ) : (
              <Text style={styles.deleteAccountText}>Delete Account</Text>
            )}
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: spacing.screenPadding },
  listContent: { padding: spacing.screenPadding, paddingBottom: 100 },

  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: spacing.screenPadding,
  },
  tab: {
    flex: 1, paddingVertical: 14, alignItems: 'center',
    flexDirection: 'row', justifyContent: 'center', gap: 6,
  },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.textPrimary },
  tabText: { fontSize: 14, fontWeight: '600', color: colors.textTertiary },
  tabTextActive: { color: colors.textPrimary },
  badge: {
    backgroundColor: colors.accent, borderRadius: 10,
    minWidth: 20, height: 20, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 6,
  },
  badgeText: { color: '#FFFFFF', fontSize: 11, fontWeight: '800' },

  plansScroll: { marginBottom: 4 },
  plansScrollContent: { gap: 10, paddingVertical: 4 },
  planCard: {
    width: 140, backgroundColor: colors.background,
    borderRadius: radii.card, padding: 12, ...shadows.card,
  },
  planCardInvited: { borderWidth: 1, borderColor: colors.accent, backgroundColor: colors.accentLight },
  planName: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, marginBottom: 6 },
  planAvatars: { fontSize: 16, marginBottom: 8 },
  planStatusBadge: {
    alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: radii.pill, backgroundColor: colors.backgroundTertiary,
  },
  planStatusDecided: { backgroundColor: 'rgba(52,168,83,0.15)' },
  planStatusCancelled: { backgroundColor: 'rgba(234,67,53,0.15)' },
  planStatusInvited: { backgroundColor: colors.accentLight },
  planStatusText: { fontSize: 11, fontWeight: '700', color: colors.accent },
  plansEmpty: { fontSize: 13, color: colors.textTertiary, textAlign: 'center', paddingVertical: 12 },

  friendCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.background, borderRadius: radii.card,
    padding: spacing.cardPadding, marginBottom: spacing.cardGap, ...shadows.card,
  },
  avatar: { fontSize: 36, marginRight: 14 },
  friendInfo: { flex: 1 },
  friendName: { fontSize: 16, fontWeight: '600', color: colors.textPrimary },
  friendUsername: { fontSize: 13, color: colors.textTertiary, marginTop: 1 },
  friendCuisines: { fontSize: 12, color: colors.accent, marginTop: 4 },

  fab: {
    position: 'absolute', bottom: 24, right: spacing.screenPadding,
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: colors.accent, justifyContent: 'center', alignItems: 'center',
    ...shadows.elevated,
  },

  requestCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.background, borderRadius: radii.card,
    padding: spacing.cardPadding, marginBottom: spacing.cardGap, ...shadows.card,
  },
  requestActions: { flexDirection: 'row', gap: 8 },
  acceptBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.accent, justifyContent: 'center', alignItems: 'center',
  },
  declineBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.backgroundTertiary, justifyContent: 'center', alignItems: 'center',
  },
  pendingBadge: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: radii.pill, backgroundColor: colors.backgroundTertiary,
  },
  pendingText: { fontSize: 12, fontWeight: '600', color: colors.textTertiary },

  addContainer: { flex: 1 },
  searchPadding: { padding: spacing.screenPadding, paddingBottom: 0 },
  searchResultCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.background, borderRadius: radii.card,
    padding: spacing.cardPadding, marginBottom: spacing.cardGap, ...shadows.card,
  },
  addBtn: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: radii.pill, backgroundColor: colors.accent },
  addBtnDisabled: { backgroundColor: colors.backgroundTertiary },
  addBtnText: { fontSize: 13, fontWeight: '700', color: '#FFFFFF' },
  addBtnTextDisabled: { color: colors.textTertiary },

  emptyEmoji: { fontSize: 48, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: colors.textSecondary, marginBottom: 4 },
  emptySubtext: { fontSize: 14, color: colors.textTertiary, textAlign: 'center' },

  sectionLabel: {
    fontSize: 11, fontWeight: '600', color: colors.textSecondary,
    textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12,
  },

  setupContainer: { padding: spacing.screenPadding, paddingTop: 40 },
  setupTitle: { fontSize: 28, fontWeight: '800', color: colors.textPrimary, marginBottom: 8 },
  setupSubtitle: { fontSize: 15, color: colors.textSecondary, marginBottom: 32 },
  emojiGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 24 },
  emojiOption: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: colors.backgroundSecondary, borderWidth: 2, borderColor: colors.border,
    justifyContent: 'center', alignItems: 'center',
  },
  emojiSelected: { borderColor: colors.accent, backgroundColor: colors.accentLight },
  emojiText: { fontSize: 28 },
  setupInput: {
    backgroundColor: colors.backgroundTertiary, borderRadius: radii.input,
    paddingHorizontal: 16, paddingVertical: 14, fontSize: 16,
    color: colors.textPrimary, marginBottom: 6,
  },
  setupHint: { fontSize: 12, color: colors.textTertiary, marginBottom: 20 },
  setupButtonRow: { marginTop: 12 },
  errorText: { color: colors.error, fontSize: 14, textAlign: 'center', marginVertical: 8 },

  footerSection: { paddingBottom: spacing.screenPadding },
  legalLinks: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', paddingVertical: 8 },
  legalText: { color: colors.textTertiary, fontSize: 12 },
  legalDot: { color: colors.textTertiary, fontSize: 12 },
  logoutBtn: {
    marginHorizontal: spacing.screenPadding, marginBottom: 4, paddingVertical: 14,
    borderRadius: radii.input, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.background, alignItems: 'center',
  },
  logoutText: { color: colors.error, fontSize: 16, fontWeight: '600' },
  deleteAccountBtn: {
    marginHorizontal: spacing.screenPadding, marginTop: 8, marginBottom: 4, paddingVertical: 14,
    alignItems: 'center',
  },
  deleteAccountText: { color: colors.textTertiary, fontSize: 13 },
});
