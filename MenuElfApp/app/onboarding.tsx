import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet, View, Text, TouchableOpacity, Image,
  ActivityIndicator, Animated, Dimensions,
} from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiGet, apiPost } from '../lib/api';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const IMAGE_SIZE = Math.min(SCREEN_WIDTH * 0.42, 180);

type QuestionOption = {
  image_url: string;
  label: string;
};

type Question = {
  question_index: number;
  option_a: QuestionOption;
  option_b: QuestionOption;
};

type Answer = {
  question_index: number;
  chosen_option: 'a' | 'b';
};

const ONBOARDING_KEY = 'menuelf_onboarding_completed';
const ONBOARDING_PROGRESS_KEY = 'menuelf_onboarding_progress';

export default function OnboardingScreen() {
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const scaleA = useRef(new Animated.Value(1)).current;
  const scaleB = useRef(new Animated.Value(1)).current;

  // Load questions and restore progress
  useEffect(() => {
    loadQuestions();
  }, []);

  const loadQuestions = async () => {
    try {
      setError('');
      const res = await apiGet('/onboarding/questions');
      if (!res.ok) throw new Error('Failed to load questions');
      const data = await res.json();
      setQuestions(data.questions || []);

      // Restore progress
      const saved = await AsyncStorage.getItem(ONBOARDING_PROGRESS_KEY);
      if (saved) {
        const progress = JSON.parse(saved);
        if (Array.isArray(progress.answers) && typeof progress.currentIndex === 'number') {
          setAnswers(progress.answers);
          setCurrentIndex(progress.currentIndex);
        }
      }
    } catch {
      setError('Could not load questions. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  const saveProgress = async (newAnswers: Answer[], newIndex: number) => {
    try {
      await AsyncStorage.setItem(ONBOARDING_PROGRESS_KEY, JSON.stringify({
        answers: newAnswers,
        currentIndex: newIndex,
      }));
    } catch {}
  };

  const handleChoice = async (option: 'a' | 'b') => {
    const question = questions[currentIndex];
    if (!question) return;

    // Animate tap
    const scaleRef = option === 'a' ? scaleA : scaleB;
    Animated.sequence([
      Animated.spring(scaleRef, { toValue: 0.92, useNativeDriver: true, friction: 5 }),
      Animated.spring(scaleRef, { toValue: 1, useNativeDriver: true, friction: 5 }),
    ]).start();

    const newAnswer: Answer = { question_index: question.question_index, chosen_option: option };
    const newAnswers = [...answers.filter(a => a.question_index !== question.question_index), newAnswer];
    setAnswers(newAnswers);

    const nextIndex = currentIndex + 1;

    if (nextIndex >= questions.length) {
      // All answered — submit
      await saveProgress(newAnswers, nextIndex);
      submitOnboarding(newAnswers);
    } else {
      // Transition to next question
      Animated.timing(fadeAnim, { toValue: 0, duration: 150, useNativeDriver: true }).start(() => {
        setCurrentIndex(nextIndex);
        saveProgress(newAnswers, nextIndex);
        Animated.timing(fadeAnim, { toValue: 1, duration: 250, useNativeDriver: true }).start();
      });
    }
  };

  const submitOnboarding = async (finalAnswers: Answer[]) => {
    setSubmitting(true);
    setError('');
    try {
      const res = await apiPost('/onboarding/complete', { answers: finalAnswers });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to save profile');
      }

      // Mark complete
      await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
      await AsyncStorage.removeItem(ONBOARDING_PROGRESS_KEY);

      // Navigate to main app
      router.replace('/(tabs)');
    } catch (e: any) {
      setError(e.message || 'Something went wrong. Please try again.');
      setSubmitting(false);
    }
  };

  const formatLabel = (label: string) =>
    label.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  // Loading state
  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#D4A574" />
        <Text style={styles.loadingText}>Loading questions...</Text>
      </View>
    );
  }

  // Error state with retry
  if (error && questions.length === 0) {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => { setLoading(true); loadQuestions(); }}>
          <Text style={styles.retryBtnText}>Try Again</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // Submitting state
  if (submitting) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#D4A574" />
        <Text style={styles.loadingText}>Building your taste profile...</Text>
      </View>
    );
  }

  const question = questions[currentIndex];
  if (!question) return null;

  return (
    <View style={styles.container}>
      {/* Progress dots */}
      <View style={styles.progressRow}>
        {questions.map((_, i) => (
          <View key={i} style={[styles.dot, i <= currentIndex ? styles.dotActive : styles.dotInactive]} />
        ))}
      </View>

      <Text style={styles.title}>Pick your vibe</Text>
      <Text style={styles.subtitle}>{currentIndex + 1} of {questions.length}</Text>

      {error ? <Text style={styles.inlineError}>{error}</Text> : null}

      <Animated.View style={[styles.optionsRow, { opacity: fadeAnim }]}>
        {/* Option A */}
        <Animated.View style={{ transform: [{ scale: scaleA }] }}>
          <TouchableOpacity
            style={styles.optionCard}
            activeOpacity={0.85}
            onPress={() => handleChoice('a')}
          >
            <Image source={{ uri: question.option_a.image_url }} style={styles.foodImage} />
            <Text style={styles.optionLabel} numberOfLines={2}>{formatLabel(question.option_a.label)}</Text>
          </TouchableOpacity>
        </Animated.View>

        <Text style={styles.orText}>or</Text>

        {/* Option B */}
        <Animated.View style={{ transform: [{ scale: scaleB }] }}>
          <TouchableOpacity
            style={styles.optionCard}
            activeOpacity={0.85}
            onPress={() => handleChoice('b')}
          >
            <Image source={{ uri: question.option_b.image_url }} style={styles.foodImage} />
            <Text style={styles.optionLabel} numberOfLines={2}>{formatLabel(question.option_b.label)}</Text>
          </TouchableOpacity>
        </Animated.View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D0D0D',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  progressRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 32,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  dotActive: {
    backgroundColor: '#D4A574',
  },
  dotInactive: {
    backgroundColor: '#333',
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
    color: '#888',
    marginBottom: 32,
  },
  optionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  optionCard: {
    alignItems: 'center',
    width: IMAGE_SIZE + 16,
  },
  foodImage: {
    width: IMAGE_SIZE,
    height: IMAGE_SIZE,
    borderRadius: 20,
    backgroundColor: '#222',
  },
  optionLabel: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 20,
  },
  orText: {
    color: '#666',
    fontSize: 16,
    fontWeight: '600',
  },
  loadingText: {
    color: '#D4A574',
    fontSize: 18,
    fontWeight: '600',
    marginTop: 16,
  },
  errorText: {
    color: '#FF6B6B',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 22,
  },
  inlineError: {
    color: '#FF6B6B',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 12,
  },
  retryBtn: {
    backgroundColor: '#D4A574',
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 12,
  },
  retryBtnText: {
    color: '#0D0D0D',
    fontSize: 16,
    fontWeight: '700',
  },
});
