import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator,
  TouchableWithoutFeedback, Keyboard, Animated, ScrollView,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { apiGet, apiPost, logInteraction } from '../lib/api';
import { colors, radii, spacing } from '../lib/theme';

const nameCache: Record<string, string> = {};

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

const stripMarkdown = (text: string): string => {
  return text
    .replace(/\*\*\*(.*?)\*\*\*/g, '$1')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/_(.*?)_/g, '$1')
    .replace(/~~(.*?)~~/g, '$1')
    .replace(/`{3}[\s\S]*?`{3}/g, '')
    .replace(/`(.*?)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '- ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
};

const toBackendHistory = (msgs: Message[]) => msgs.map(m => ({
  role: m.role,
  content: m.content,
}));

const QUICK_SUGGESTIONS = ["What's popular?", "Spicy options", "Under $20"];

function TypingIndicator() {
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animate = (dot: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(dot, { toValue: -6, duration: 300, useNativeDriver: true }),
          Animated.timing(dot, { toValue: 0, duration: 300, useNativeDriver: true }),
        ])
      );
    animate(dot1, 0).start();
    animate(dot2, 150).start();
    animate(dot3, 300).start();
  }, []);

  return (
    <View style={styles.typingContainer}>
      {[dot1, dot2, dot3].map((dot, i) => (
        <Animated.View
          key={i}
          style={[styles.typingDot, { transform: [{ translateY: dot }] }]}
        />
      ))}
    </View>
  );
}

export default function ChatScreen() {
  const { restaurant, dish } = useLocalSearchParams<{ restaurant: string; dish?: string }>();
  const router = useRouter();

  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showTyping, setShowTyping] = useState(false);
  const [displayName, setDisplayName] = useState(restaurant || '');
  const flatListRef = useRef<FlatList>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const messagesRef = useRef<Message[]>([]);
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => { messagesRef.current = messages; }, [messages]);

  useEffect(() => {
    if (!restaurant) return;
    if (nameCache[restaurant]) {
      setDisplayName(nameCache[restaurant]);
      return;
    }
    (async () => {
      try {
        const res = await apiGet('/restaurants?q=');
        const data = await res.json();
        for (const r of data.restaurants || []) {
          nameCache[r.slug] = r.name;
        }
        if (nameCache[restaurant]) setDisplayName(nameCache[restaurant]);
      } catch {}
    })();
  }, [restaurant]);

  useEffect(() => {
    if (!restaurant || messages.length > 0) return;

    if (dish) {
      const initialMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `You picked ${dish}! Let me tell you about it...`,
      };
      setMessages([initialMsg]);

      setTimeout(async () => {
        const hiddenQuery = `Tell me briefly about ${dish} in one sentence, include the price, and ask if I want to know more.`;
        setShowTyping(true);
        setIsLoading(true);
        try {
          const res = await apiPost('/chat', {
            restaurant, message: hiddenQuery,
            history: [{ role: 'assistant', content: initialMsg.content }],
            session_id: sessionIdRef.current,
          });
          const data = await res.json();
          if (data.session_id) sessionIdRef.current = data.session_id;
          setMessages(prev => [...prev, {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: data.reply || "Here's what I found about that dish!",
          }]);
        } catch (err) { console.error(err); }
        finally { setIsLoading(false); setShowTyping(false); }
      }, 500);
    } else {
      setShowTyping(true);
      setTimeout(async () => {
        try {
          const res = await apiPost('/chat/start', { restaurant_slug: restaurant });
          const data = await res.json();
          if (data.session_id) sessionIdRef.current = data.session_id;
          setShowTyping(false);
          setMessages([{
            id: Date.now().toString(),
            role: 'assistant',
            content: data.reply || 'Hey! How can I help you?',
          }]);
        } catch {
          setShowTyping(false);
          setMessages([{
            id: Date.now().toString(),
            role: 'assistant',
            content: 'Hey! How can I help you?',
          }]);
        }
      }, 1000);
    }

    logInteraction('restaurant_chat_open', { restaurant_slug: restaurant });
  }, [restaurant, dish]);

  const handleBack = useCallback(() => { router.back(); }, [router]);

  const sendMessage = async (text?: string) => {
    const msgText = (text || inputText).trim();
    if (!msgText) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: msgText };

    logInteraction('chat_message', { restaurant_slug: restaurant, message: userMessage.content, role: 'user' });

    const previousHistory = [...messages];
    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);
    setShowTyping(true);

    try {
      const res = await apiPost('/chat', {
        restaurant,
        message: userMessage.content,
        history: toBackendHistory(previousHistory),
        session_id: sessionIdRef.current,
      });
      if (!res.ok) throw new Error('Failed to fetch from backend');
      const data = await res.json();
      if (data.session_id) sessionIdRef.current = data.session_id;

      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.reply || "Sorry, I didn't get a response. Please try again.",
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, something went wrong. Is the FastAPI server running?',
      }]);
    } finally {
      setIsLoading(false);
      setShowTyping(false);
    }
  };

  const renderMessage = ({ item, index }: { item: Message; index: number }) => {
    const isUser = item.role === 'user';
    return (
      <MessageBubble isUser={isUser} index={index}>
        <Text style={[styles.messageText, isUser ? styles.userText : styles.assistantText]}>
          {isUser ? item.content : stripMarkdown(item.content)}
        </Text>
      </MessageBubble>
    );
  };

  return (
    <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={22} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle} numberOfLines={1}>{displayName}</Text>
          <View style={{ width: 44 }} />
        </View>

        <KeyboardAvoidingView
          style={styles.keyboardView}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 24}
        >
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={item => item.id}
            renderItem={renderMessage}
            contentContainerStyle={styles.chatContent}
            keyboardDismissMode="on-drag"
            onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
            onLayout={() => flatListRef.current?.scrollToEnd({ animated: true })}
            ListFooterComponent={showTyping ? <TypingIndicator /> : null}
          />

          {messages.length <= 2 && (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.suggestionsRow}
            >
              {QUICK_SUGGESTIONS.map((s) => (
                <TouchableOpacity key={s} style={styles.suggestionPill} onPress={() => sendMessage(s)}>
                  <Text style={styles.suggestionText}>{s}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          )}

          <View style={styles.inputContainer}>
            <TextInput
              style={styles.textInput}
              value={inputText}
              onChangeText={setInputText}
              placeholder="Ask about the menu..."
              placeholderTextColor={colors.textTertiary}
              multiline
              maxLength={300}
            />
            <TouchableOpacity
              style={[styles.sendButton, !inputText.trim() && styles.sendButtonDisabled]}
              onPress={() => sendMessage()}
              disabled={!inputText.trim() || isLoading}
            >
              {isLoading ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <Ionicons name="arrow-up" size={20} color="#FFFFFF" />
              )}
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </TouchableWithoutFeedback>
  );
}

function MessageBubble({ isUser, children, index }: { isUser: boolean; children: React.ReactNode; index: number }) {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(10)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, { toValue: 1, duration: 300, useNativeDriver: true }),
      Animated.timing(slideAnim, { toValue: 0, duration: 300, useNativeDriver: true }),
    ]).start();
  }, []);

  return (
    <Animated.View style={[
      styles.messageBubble,
      isUser ? styles.userBubble : styles.assistantBubble,
      { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
    ]}>
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: spacing.screenPadding, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: colors.border,
    backgroundColor: colors.background,
  },
  backButton: { width: 44, padding: 8 },
  headerTitle: {
    flex: 1, fontSize: 18, fontWeight: '700',
    color: colors.textPrimary, textAlign: 'center',
  },
  keyboardView: { flex: 1 },
  chatContent: { padding: spacing.screenPadding, gap: 12 },
  messageBubble: { maxWidth: '80%', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 20 },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: colors.backgroundTertiary,
    borderBottomLeftRadius: 4,
  },
  messageText: { fontSize: 16, lineHeight: 22 },
  userText: { color: '#FFFFFF' },
  assistantText: { color: colors.textPrimary },

  typingContainer: {
    flexDirection: 'row', alignSelf: 'flex-start',
    backgroundColor: colors.backgroundTertiary,
    borderRadius: 20, borderBottomLeftRadius: 4,
    paddingHorizontal: 16, paddingVertical: 14, gap: 5,
  },
  typingDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.accent },

  suggestionsRow: { paddingHorizontal: spacing.screenPadding, paddingBottom: 8, gap: 8 },
  suggestionPill: {
    borderWidth: 1, borderColor: colors.border,
    borderRadius: radii.pill, paddingHorizontal: 16, paddingVertical: 8, marginRight: 8,
  },
  suggestionText: { color: colors.accent, fontSize: 13, fontWeight: '600' },

  inputContainer: {
    flexDirection: 'row', paddingHorizontal: spacing.screenPadding,
    paddingVertical: 12, paddingBottom: Platform.OS === 'ios' ? 24 : 12,
    borderTopWidth: 1, borderTopColor: colors.border,
    backgroundColor: colors.background, alignItems: 'flex-end',
  },
  textInput: {
    flex: 1, minHeight: 44, maxHeight: 120,
    backgroundColor: colors.backgroundTertiary,
    borderWidth: 1, borderColor: colors.border, borderRadius: 22,
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12,
    fontSize: 16, color: colors.textPrimary, marginRight: 12,
  },
  sendButton: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: colors.accent,
    justifyContent: 'center', alignItems: 'center',
  },
  sendButtonDisabled: { backgroundColor: colors.backgroundTertiary },
});
