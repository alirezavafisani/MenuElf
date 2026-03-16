import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet, View, Text, TouchableOpacity, Image,
  ActivityIndicator, Animated, Dimensions,
} from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiGet, apiPost } from '../lib/api';
import { colors, radii } from '../lib/theme';
import GoldButton from '../components/ui/GoldButton';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const CARD_HEIGHT = (SCREEN_HEIGHT - 280) / 2;

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
  const [selected, setSelected] = useState<'a' | 'b' | null>(null);
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const slideAnim = useRef(new Animated.Value(0)).current;
  const borderAnimA = useRef(new Animated.Value(0)).current;
  const borderAnimB = useRef(new Animated.Value(0)).current;
  const loadingDotAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => { loadQuestions(); }, []);

  // Loading dot animation for submitting state
  useEffect(() => {
    if (submitting) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(loadingDotAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
          Animated.timing(loadingDotAnim, { toValue: 0, duration: 800, useNativeDriver: true }),
        ])
      ).start();
    }
  }, [submitting]);

  const loadQuestions = async () => {
    try {
      setError('');
      const res = await apiGet('/onboarding/questions');
      if (!res.ok) throw new Error('Failed to load questions');
      const data = await res.json();
      setQuestions(data.questions || []);

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

    // Show gold border on selected card
    setSelected(option);
    const borderRef = option === 'a' ? borderAnimA : borderAnimB;
    Animated.timing(borderRef, { toValue: 1, duration: 200, useNativeDriver: false }).start();

    const newAnswer: Answer = { question_index: question.question_index, chosen_option: option };
    const newAnswers = [...answers.filter(a => a.question_index !== question.question_index), newAnswer];
    setAnswers(newAnswers);

    const nextIndex = currentIndex + 1;

    // Delay before transition
    setTimeout(() => {
      if (nextIndex >= questions.length) {
        saveProgress(newAnswers, nextIndex);
        submitOnboarding(newAnswers);
      } else {
        // Slide + fade transition
        Animated.parallel([
          Animated.timing(fadeAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
          Animated.timing(slideAnim, { toValue: -30, duration: 200, useNativeDriver: true }),
        ]).start(() => {
          setCurrentIndex(nextIndex);
          setSelected(null);
          borderAnimA.setValue(0);
          borderAnimB.setValue(0);
          slideAnim.setValue(30);
          saveProgress(newAnswers, nextIndex);
          Animated.parallel([
            Animated.timing(fadeAnim, { toValue: 1, duration: 300, useNativeDriver: true }),
            Animated.timing(slideAnim, { toValue: 0, duration: 300, useNativeDriver: true }),
          ]).start();
        });
      }
    }, 300);
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
      await AsyncStorage.setItem(ONBOARDING_KEY, 'true');
      await AsyncStorage.removeItem(ONBOARDING_PROGRESS_KEY);
      router.replace('/(tabs)');
    } catch (e: any) {
      setError(e.message || 'Something went wrong. Please try again.');
      setSubmitting(false);
    }
  };

  const formatLabel = (label: string) =>
    label.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color={colors.goldPrimary} />
        <Text style={styles.loadingText}>Loading questions...</Text>
      </View>
    );
  }

  if (error && questions.length === 0) {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>{error}</Text>
        <GoldButton title="Try Again" onPress={() => { setLoading(true); loadQuestions(); }} inline />
      </View>
    );
  }

  if (submitting) {
    return (
      <View style={styles.container}>
        <Animated.View style={{ opacity: loadingDotAnim.interpolate({ inputRange: [0, 1], outputRange: [0.4, 1] }) }}>
          <Text style={styles.buildingEmoji}>&#9733;</Text>
        </Animated.View>
        <Text style={styles.buildingText}>Building your taste profile...</Text>
        <Text style={styles.buildingSubtext}>This will only take a moment</Text>
      </View>
    );
  }

  const question = questions[currentIndex];
  if (!question) return null;

  const borderColorA = borderAnimA.interpolate({
    inputRange: [0, 1],
    outputRange: [colors.border, colors.goldPrimary],
  });
  const borderColorB = borderAnimB.interpolate({
    inputRange: [0, 1],
    outputRange: [colors.border, colors.goldPrimary],
  });

  return (
    <View style={styles.container}>
      {/* Progress dots */}
      <View style={styles.progressRow}>
        {questions.map((_, i) => (
          <View
            key={i}
            style={[
              styles.dot,
              i < currentIndex ? styles.dotCompleted :
              i === currentIndex ? styles.dotActive : styles.dotInactive,
            ]}
          />
        ))}
      </View>

      <Text style={styles.heading}>What excites your taste buds?</Text>
      <Text style={styles.counter}>{currentIndex + 1} of {questions.length}</Text>

      {error ? <Text style={styles.inlineError}>{error}</Text> : null}

      <Animated.View style={[styles.optionsContainer, { opacity: fadeAnim, transform: [{ translateY: slideAnim }] }]}>
        {/* Option A */}
        <Animated.View style={[styles.optionCard, { borderColor: borderColorA }]}>
          <TouchableOpacity
            style={styles.optionTouchable}
            activeOpacity={0.85}
            onPress={() => handleChoice('a')}
          >
            <Image source={{ uri: question.option_a.image_url }} style={styles.foodImage} />
            <View style={styles.labelOverlay}>
              <Text style={styles.optionLabel} numberOfLines={2}>{formatLabel(question.option_a.label)}</Text>
            </View>
          </TouchableOpacity>
        </Animated.View>

        {/* Option B */}
        <Animated.View style={[styles.optionCard, { borderColor: borderColorB }]}>
          <TouchableOpacity
            style={styles.optionTouchable}
            activeOpacity={0.85}
            onPress={() => handleChoice('b')}
          >
            <Image source={{ uri: question.option_b.image_url }} style={styles.foodImage} />
            <View style={styles.labelOverlay}>
              <Text style={styles.optionLabel} numberOfLines={2}>{formatLabel(question.option_b.label)}</Text>
            </View>
          </TouchableOpacity>
        </Animated.View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  progressRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 32,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  dotActive: {
    backgroundColor: colors.goldPrimary,
    width: 24,
    borderRadius: 5,
  },
  dotCompleted: {
    backgroundColor: colors.goldDark,
  },
  dotInactive: {
    backgroundColor: colors.surfaceElevated,
  },
  heading: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: 4,
  },
  counter: {
    fontSize: 14,
    color: colors.textTertiary,
    marginBottom: 28,
  },
  inlineError: {
    color: colors.error,
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 12,
  },
  optionsContainer: {
    width: '100%',
    gap: 16,
  },
  optionCard: {
    borderRadius: radii.card,
    borderWidth: 2,
    overflow: 'hidden',
    height: CARD_HEIGHT,
  },
  optionTouchable: {
    flex: 1,
  },
  foodImage: {
    width: '100%',
    height: '100%',
    backgroundColor: colors.surface,
  },
  labelOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingVertical: 14,
    paddingHorizontal: 16,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  optionLabel: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '700',
    textAlign: 'center',
  },
  loadingText: {
    color: colors.goldPrimary,
    fontSize: 18,
    fontWeight: '600',
    marginTop: 16,
  },
  errorText: {
    color: colors.error,
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 22,
  },
  buildingEmoji: {
    fontSize: 48,
    color: colors.goldPrimary,
    marginBottom: 16,
  },
  buildingText: {
    color: colors.goldPrimary,
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 8,
  },
  buildingSubtext: {
    color: colors.textSecondary,
    fontSize: 14,
  },
});
