import { useState, useRef, useEffect } from 'react';
import { chatWithRestaurant } from '../api';
import type { ChatMessage } from '../types';

interface ChatPanelProps {
  slug: string;
  name: string;
  onClose: () => void;
}

export default function ChatPanel({ slug, name, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef(false);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Send initial greeting
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const initChat = async () => {
      setLoading(true);
      try {
        const res = await chatWithRestaurant(slug, 'Hi! What do you recommend?', []);
        setMessages([{ role: 'assistant', content: res.reply }]);
      } catch {
        setMessages([
          {
            role: 'assistant',
            content: `Welcome! I know everything about ${name}'s menu. What are you in the mood for?`,
          },
        ]);
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    };
    initChat();
  }, [slug, name]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading || rateLimited) return;

    setInput('');
    setError('');
    const userMsg: ChatMessage = { role: 'user', content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setLoading(true);

    try {
      const res = await chatWithRestaurant(slug, text, messages);
      setMessages([...updated, { role: 'assistant', content: res.reply }]);
    } catch (err) {
      if (err instanceof Error && err.message === 'RATE_LIMITED') {
        setRateLimited(true);
        setError('Rate limit reached. Please try again in a bit.');
      } else {
        setError('Failed to get response. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[100] md:bg-transparent md:backdrop-blur-none"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 bottom-0 w-full md:w-[400px] bg-white shadow-2xl z-[101] flex flex-col animate-slide-in">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200 bg-white">
          <div className="min-w-0">
            <h3 className="font-semibold text-stone-900 truncate">{name}</h3>
            <p className="text-xs text-stone-500">AI Menu Assistant</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-stone-100 transition-colors flex-shrink-0"
            aria-label="Close chat"
          >
            <svg className="w-5 h-5 text-stone-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`chat-message-enter flex ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-accent text-white rounded-br-md'
                    : 'bg-stone-100 text-stone-800 rounded-bl-md'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-stone-100 text-stone-500 px-4 py-2.5 rounded-2xl rounded-bl-md text-sm">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce" style={{ animationDelay: '0ms' }}>·</span>
                  <span className="animate-bounce" style={{ animationDelay: '150ms' }}>·</span>
                  <span className="animate-bounce" style={{ animationDelay: '300ms' }}>·</span>
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="text-center">
              <p className="text-xs text-red-500">{error}</p>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-stone-200 px-4 py-3 bg-white">
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={rateLimited ? 'Rate limit reached...' : 'Ask about the menu...'}
              disabled={rateLimited}
              className="flex-1 px-4 py-2.5 text-sm bg-stone-50 border border-stone-200 rounded-full focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 disabled:opacity-50 transition-all"
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading || rateLimited}
              className="p-2.5 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white rounded-full transition-colors flex-shrink-0"
              aria-label="Send message"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
          <p className="text-[10px] text-stone-400 text-center mt-2">
            Free preview · 30 messages per hour
          </p>
        </div>
      </div>

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        .animate-slide-in {
          animation: slideIn 0.3s ease-out;
        }
      `}</style>
    </>
  );
}
