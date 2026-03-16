import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity,
  FlatList, ActivityIndicator, Platform, KeyboardAvoidingView,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiGet, apiPost } from '../../lib/api';
import { colors, radii, spacing } from '../../lib/theme';

type Message = {
  id: string;
  plan_id: string;
  sender_id: string | null;
  sender_type: 'user' | 'ai';
  content: string;
  created_at: string;
  sender_profile?: {
    username: string;
    display_name: string;
    avatar_emoji: string;
  } | null;
};

type PlanMember = {
  user_id: string;
  status: string;
  profile?: { username: string; display_name: string; avatar_emoji: string };
};

type Plan = {
  id: string;
  name: string;
  status: string;
  creator_id: string;
  decided_restaurant_slug?: string | null;
  members?: PlanMember[];
};

export default function GroupChatScreen() {
  const { id: planId } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [plan, setPlan] = useState<Plan | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(true);
  const flatListRef = useRef<FlatList>(null);
  const lastTimestampRef = useRef<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string>('');

  // Get current user id
  useEffect(() => {
    (async () => {
      try {
        const { supabase } = await import('../../lib/supabase');
        const { data } = await supabase.auth.getSession();
        if (data.session?.user?.id) {
          setCurrentUserId(data.session.user.id);
        }
      } catch {}
    })();
  }, []);

  // Load plan details
  useEffect(() => {
    if (!planId) return;
    loadPlan();
  }, [planId]);

  // Polling for new messages
  useEffect(() => {
    if (!planId) return;

    // Initial load
    fetchMessages();

    // Poll every 3 seconds
    pollIntervalRef.current = setInterval(() => {
      fetchMessages(true);
    }, 3000);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [planId]);

  const loadPlan = async () => {
    setLoadingPlan(true);
    try {
      const res = await apiGet(`/plans/${planId}`);
      if (res.ok) {
        const data = await res.json();
        setPlan(data.plan);
      }
    } catch {}
    finally { setLoadingPlan(false); }
  };

  const fetchMessages = async (polling = false) => {
    try {
      const afterParam = polling && lastTimestampRef.current
        ? `?after=${encodeURIComponent(lastTimestampRef.current)}`
        : '';
      const res = await apiGet(`/plans/${planId}/messages${afterParam}`);
      if (res.ok) {
        const data = await res.json();
        const newMsgs: Message[] = data.messages ?? [];
        if (polling && lastTimestampRef.current) {
          // Append only new messages
          if (newMsgs.length > 0) {
            setMessages(prev => {
              const existingIds = new Set(prev.map(m => m.id));
              const toAdd = newMsgs.filter(m => !existingIds.has(m.id));
              if (toAdd.length === 0) return prev;
              const merged = [...prev, ...toAdd];
              lastTimestampRef.current = merged[merged.length - 1].created_at;
              return merged;
            });
            setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
          }
        } else {
          setMessages(newMsgs);
          if (newMsgs.length > 0) {
            lastTimestampRef.current = newMsgs[newMsgs.length - 1].created_at;
          }
          setTimeout(() => flatListRef.current?.scrollToEnd({ animated: false }), 100);
        }
      }
    } catch {}
  };

  const sendMessage = async () => {
    const text = inputText.trim();
    if (!text || sending) return;

    // Optimistic add
    const optimisticMsg: Message = {
      id: `temp-${Date.now()}`,
      plan_id: planId || '',
      sender_id: currentUserId,
      sender_type: 'user',
      content: text,
      created_at: new Date().toISOString(),
      sender_profile: null,
    };
    setMessages(prev => [...prev, optimisticMsg]);
    setInputText('');
    setSending(true);
    setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 50);

    try {
      const res = await apiPost(`/plans/${planId}/messages`, { content: text });
      if (res.ok) {
        const data = await res.json();
        // Replace optimistic with real
        setMessages(prev => {
          const filtered = prev.filter(m => m.id !== optimisticMsg.id);
          const toAdd = [data.message];
          if (data.ai_response) toAdd.push(data.ai_response);
          const merged = [...filtered, ...toAdd];
          if (merged.length > 0) {
            lastTimestampRef.current = merged[merged.length - 1].created_at;
          }
          return merged;
        });
        setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
      } else {
        // Revert optimistic
        setMessages(prev => prev.filter(m => m.id !== optimisticMsg.id));
        setInputText(text);
      }
    } catch {
      setMessages(prev => prev.filter(m => m.id !== optimisticMsg.id));
      setInputText(text);
    } finally {
      setSending(false);
    }
  };

  const isCancelled = plan?.status === 'cancelled';
  const isDecided = plan?.status === 'decided';

  const renderMessage = ({ item }: { item: Message }) => {
    const isAI = item.sender_type === 'ai';
    const isMe = item.sender_id === currentUserId;

    return (
      <View style={[
        styles.msgRow,
        isMe ? styles.msgRowRight : styles.msgRowLeft,
      ]}>
        {!isMe && (
          <Text style={styles.senderLabel}>
            {isAI ? 'MenuElf 🧝' : item.sender_profile?.display_name ?? item.sender_profile?.username ?? 'User'}
          </Text>
        )}
        <View style={[
          styles.bubble,
          isMe ? styles.bubbleUser : isAI ? styles.bubbleAI : styles.bubbleOther,
        ]}>
          <Text style={styles.msgText}>{item.content}</Text>
        </View>
      </View>
    );
  };

  if (loadingPlan) {
    return (
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.goldPrimary} />
        </View>
      </SafeAreaView>
    );
  }

  const joinedAvatars = (plan?.members ?? [])
    .filter(m => m.status === 'joined')
    .map(m => m.profile?.avatar_emoji ?? '🧝')
    .slice(0, 5);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle} numberOfLines={1}>{plan?.name ?? 'Group Chat'}</Text>
          <Text style={styles.headerAvatars}>{joinedAvatars.join(' ')}</Text>
        </View>
        <TouchableOpacity
          onPress={() => router.push(`/group/recommendations?planId=${planId}`)}
          style={styles.recsBtn}
        >
          <Ionicons name="restaurant-outline" size={20} color={colors.goldPrimary} />
        </TouchableOpacity>
      </View>

      {/* Banners */}
      {isCancelled && (
        <View style={styles.banner}>
          <Text style={styles.bannerText}>This plan was cancelled</Text>
        </View>
      )}
      {isDecided && (
        <View style={[styles.banner, styles.bannerSuccess]}>
          <Text style={styles.bannerText}>
            Group chose {plan?.decided_restaurant_slug?.replace(/-/g, ' ') ?? 'a restaurant'}!
          </Text>
        </View>
      )}

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 24}
      >
        {/* Messages */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={item => item.id}
          renderItem={renderMessage}
          contentContainerStyle={styles.messagesList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: false })}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.emptyText}>No messages yet. Start the conversation!</Text>
            </View>
          }
        />

        {/* Input */}
        {!isCancelled && (
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.textInput}
              value={inputText}
              onChangeText={setInputText}
              placeholder="Message the group..."
              placeholderTextColor={colors.textTertiary}
              multiline
              maxLength={500}
              editable={!sending}
            />
            <TouchableOpacity
              style={[styles.sendBtn, (!inputText.trim() || sending) && styles.sendBtnDisabled]}
              onPress={sendMessage}
              disabled={!inputText.trim() || sending}
            >
              {sending ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <Ionicons name="arrow-up" size={20} color="#FFFFFF" />
              )}
            </TouchableOpacity>
          </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  emptyText: { fontSize: 15, color: colors.textSecondary, textAlign: 'center' },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.screenPadding,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: { width: 44, padding: 8 },
  headerCenter: { flex: 1, alignItems: 'center' },
  headerTitle: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  headerAvatars: { fontSize: 14, marginTop: 2 },
  recsBtn: { width: 44, alignItems: 'flex-end', padding: 8 },

  // Banner
  banner: {
    backgroundColor: colors.surfaceElevated,
    paddingVertical: 10,
    paddingHorizontal: spacing.screenPadding,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  bannerSuccess: {
    backgroundColor: 'rgba(212,165,116,0.15)',
  },
  bannerText: { fontSize: 14, fontWeight: '600', color: colors.goldPrimary, textAlign: 'center' },

  // Messages
  messagesList: {
    padding: spacing.screenPadding,
    paddingBottom: 8,
    gap: 10,
  },
  msgRow: { maxWidth: '85%' },
  msgRowLeft: { alignSelf: 'flex-start' },
  msgRowRight: { alignSelf: 'flex-end' },
  senderLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textTertiary,
    marginBottom: 3,
    marginLeft: 4,
  },
  bubble: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 18,
  },
  bubbleUser: {
    backgroundColor: colors.userBubble,
    borderBottomRightRadius: 4,
  },
  bubbleOther: {
    backgroundColor: colors.surface,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bubbleAI: {
    backgroundColor: colors.surface,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.goldPrimary,
  },
  msgText: { fontSize: 15, color: colors.textPrimary, lineHeight: 21 },

  // Input
  inputContainer: {
    flexDirection: 'row',
    paddingHorizontal: spacing.screenPadding,
    paddingVertical: 10,
    paddingBottom: Platform.OS === 'ios' ? 24 : 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.background,
    alignItems: 'flex-end',
  },
  textInput: {
    flex: 1,
    minHeight: 44,
    maxHeight: 100,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 12,
    fontSize: 15,
    color: colors.textPrimary,
    marginRight: 10,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.goldDark,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: colors.surfaceElevated,
  },
});
