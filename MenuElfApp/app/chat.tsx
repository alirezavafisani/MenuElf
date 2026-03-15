import { StyleSheet, View, Text, TextInput, TouchableOpacity, FlatList, KeyboardAvoidingView, Platform, ActivityIndicator, TouchableWithoutFeedback, Keyboard } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState, useRef, useEffect, useCallback } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';
import { apiGet, apiPost, logInteraction } from '../lib/api';

// Map slug -> display name (fetched once)
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
    content: m.content
}));

export default function ChatScreen() {
    const { restaurant, dish } = useLocalSearchParams<{ restaurant: string, dish?: string }>();
    const router = useRouter();

    const [inputText, setInputText] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [displayName, setDisplayName] = useState(restaurant || '');
    const flatListRef = useRef<FlatList>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const messagesRef = useRef<Message[]>([]);
    const sessionIdRef = useRef<string | null>(null);

    // Keep messagesRef in sync
    useEffect(() => {
        messagesRef.current = messages;
    }, [messages]);

    // Fetch the proper display name for this restaurant slug
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
            } catch { }
        })();
    }, [restaurant]);

    // Initialize chat: use /chat/start for proactive message, or fall back to dish-specific query
    useEffect(() => {
        if (!restaurant || messages.length > 0) return;

        if (dish) {
            // Dish-specific flow: show dish pick then query backend
            const initialMsg: Message = {
                id: Date.now().toString(),
                role: 'assistant',
                content: `You picked ${dish}! Let me tell you about it...`
            };
            setMessages([initialMsg]);

            setTimeout(async () => {
                const hiddenQuery = `Tell me briefly about ${dish} in one sentence, include the price, and ask if I want to know more.`;
                setIsLoading(true);
                try {
                    const res = await apiPost('/chat', {
                        restaurant: restaurant,
                        message: hiddenQuery,
                        history: [{ role: 'assistant', content: initialMsg.content }],
                        session_id: sessionIdRef.current,
                    });
                    const data = await res.json();
                    if (data.session_id) sessionIdRef.current = data.session_id;
                    setMessages(prev => [...prev, {
                        id: (Date.now() + 1).toString(),
                        role: 'assistant',
                        content: data.reply
                    }]);
                } catch (err) {
                    console.error(err);
                } finally {
                    setIsLoading(false);
                }
            }, 500);
        } else {
            // Proactive flow: call /chat/start for personalized greeting
            (async () => {
                setIsLoading(true);
                try {
                    const res = await apiPost('/chat/start', { restaurant_slug: restaurant });
                    const data = await res.json();
                    if (data.session_id) sessionIdRef.current = data.session_id;
                    setMessages([{
                        id: Date.now().toString(),
                        role: 'assistant',
                        content: data.reply || 'Hey! How can I help you?'
                    }]);
                } catch {
                    // Fallback
                    setMessages([{
                        id: Date.now().toString(),
                        role: 'assistant',
                        content: 'Hey! How can I help you?'
                    }]);
                } finally {
                    setIsLoading(false);
                }
            })();
        }

        // Log chat open
        logInteraction('restaurant_chat_open', { restaurant_slug: restaurant });
    }, [restaurant, dish]);

    const handleBack = useCallback(() => {
        router.back();
    }, [router]);

    const sendMessage = async () => {
        if (!inputText.trim()) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: inputText.trim()
        };

        // Log the user message interaction
        logInteraction('chat_message', {
            restaurant_slug: restaurant,
            message: userMessage.content,
            role: 'user',
        });

        const previousHistory = [...messages];
        setMessages(prev => [...prev, userMessage]);
        setInputText('');
        setIsLoading(true);

        try {
            const payload = {
                restaurant: restaurant,
                message: userMessage.content,
                history: toBackendHistory(previousHistory),
                session_id: sessionIdRef.current,
            };

            const res = await apiPost('/chat', payload);
            if (!res.ok) throw new Error('Failed to fetch from backend');
            const data = await res.json();
            if (data.session_id) sessionIdRef.current = data.session_id;

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.reply
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (err) {
            console.error(err);
            setMessages(prev => [
                ...prev,
                { id: (Date.now() + 1).toString(), role: 'assistant', content: 'Sorry, something went wrong. Is the FastAPI server running?' }
            ]);
        } finally {
            setIsLoading(false);
        }
    };

    const renderMessage = ({ item }: { item: Message }) => {
        const isUser = item.role === 'user';
        return (
            <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
                <Text style={[styles.messageText, isUser ? styles.userText : styles.assistantText]}>
                    {isUser ? item.content : stripMarkdown(item.content)}
                </Text>
            </View>
        );
    };

    return (
        <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
            <View style={styles.header}>
                <TouchableOpacity style={styles.backButton} onPress={handleBack}>
                    <Text style={styles.backText}>← Back</Text>
                </TouchableOpacity>
                <Text style={styles.headerTitle} numberOfLines={1}>{displayName}</Text>
                <View style={{ width: 60 }} />
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
                    ListFooterComponent={isLoading && messages.length > 0 ? (
                        <View style={styles.typingIndicator}>
                            <Text style={styles.typingText}>MenuElf is typing...</Text>
                        </View>
                    ) : null}
                />

                <View style={styles.inputContainer}>
                    <TextInput
                        style={styles.textInput}
                        value={inputText}
                        onChangeText={setInputText}
                        placeholder="Ask about the menu..."
                        placeholderTextColor="#7A7A7A"
                        multiline
                        maxLength={300}
                    />
                    <TouchableOpacity
                        style={[styles.sendButton, !inputText.trim() && styles.sendButtonDisabled]}
                        onPress={sendMessage}
                        disabled={!inputText.trim() || isLoading}
                    >
                        {isLoading ? (
                            <ActivityIndicator color="#FFFFFF" size="small" />
                        ) : (
                            <Text style={styles.sendButtonText}>↑</Text>
                        )}
                    </TouchableOpacity>
                </View>
            </KeyboardAvoidingView>
        </SafeAreaView>
        </TouchableWithoutFeedback>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#FBF7F4' },
    header: {
        flexDirection: 'row', alignItems: 'center',
        paddingHorizontal: 16, paddingVertical: 12,
        borderBottomWidth: 1, borderBottomColor: '#E8E0D8', backgroundColor: '#FFFFFF',
    },
    backButton: { padding: 8, width: 60 },
    backText: { color: '#D4754E', fontSize: 16, fontWeight: '600' },
    headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: '#1A1A1A', textAlign: 'center' },
    keyboardView: { flex: 1 },
    chatContent: { padding: 16, gap: 12 },
    messageBubble: { maxWidth: '80%', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 20 },
    userBubble: { alignSelf: 'flex-end', backgroundColor: '#D4754E', borderBottomRightRadius: 4 },
    assistantBubble: { alignSelf: 'flex-start', backgroundColor: '#FFFFFF', borderBottomLeftRadius: 4, borderWidth: 1, borderColor: '#E8E0D8' },
    messageText: { fontSize: 16, lineHeight: 22 },
    userText: { color: '#FFFFFF' },
    assistantText: { color: '#1A1A1A' },
    typingIndicator: {
        alignSelf: 'flex-start',
        paddingHorizontal: 16,
        paddingVertical: 8,
    },
    typingText: {
        fontSize: 14,
        color: '#999',
        fontStyle: 'italic',
    },
    inputContainer: {
        flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 12,
        paddingBottom: Platform.OS === 'ios' ? 24 : 12,
        borderTopWidth: 1, borderTopColor: '#E8E0D8', backgroundColor: '#FFFFFF', alignItems: 'flex-end',
    },
    textInput: {
        flex: 1, minHeight: 44, maxHeight: 120, backgroundColor: '#FBF7F4',
        borderWidth: 1, borderColor: '#E8E0D8', borderRadius: 22,
        paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12,
        fontSize: 16, color: '#1A1A1A', marginRight: 12,
    },
    sendButton: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#D4754E', justifyContent: 'center', alignItems: 'center' },
    sendButtonDisabled: { backgroundColor: '#E8E0D8' },
    sendButtonText: { color: '#FFFFFF', fontSize: 24, fontWeight: '700', marginTop: -2 },
});
