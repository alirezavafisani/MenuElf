import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, ActivityIndicator, View } from 'react-native';
import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { supabase } from '../lib/supabase';
import { apiGet } from '../lib/api';
import { colors } from '../lib/theme';
import type { Session } from '@supabase/supabase-js';
import LoginScreen from './login';
import OnboardingScreen from './onboarding';

const ONBOARDING_KEY = 'menuelf_onboarding_completed';

export default function RootLayout() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [onboardingDone, setOnboardingDone] = useState<boolean | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s);
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      if (s?.user?.id) {
        checkOnboarding(s);
      } else {
        setOnboardingDone(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session) {
      checkOnboarding(session);
    }
  }, [session]);

  const checkOnboarding = async (sess: Session) => {
    const cachedKey = `${ONBOARDING_KEY}_${sess.user.id}`;
    const cached = await AsyncStorage.getItem(cachedKey);
    if (cached === 'true') {
      setOnboardingDone(true);
      return;
    }

    try {
      const res = await apiGet('/profile/taste');
      if (res.ok) {
        const profile = await res.json();
        if (profile.onboarding_completed) {
          await AsyncStorage.setItem(cachedKey, 'true');
          setOnboardingDone(true);
          return;
        }
      }
    } catch {}

    setOnboardingDone(false);
  };

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background }}>
        <ActivityIndicator size="large" color={colors.goldPrimary} />
      </View>
    );
  }

  if (!session) {
    return (
      <>
        <StatusBar style="light" />
        <LoginScreen />
      </>
    );
  }

  if (onboardingDone === null) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background }}>
        <ActivityIndicator size="large" color={colors.goldPrimary} />
      </View>
    );
  }

  if (!onboardingDone) {
    return (
      <>
        <StatusBar style="light" />
        <OnboardingScreen />
      </>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
      }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="chat"
          options={{
            headerShown: false,
            presentation: 'modal',
            animation: 'slide_from_bottom',
          }}
        />
        <Stack.Screen
          name="group/create"
          options={{ headerShown: false, animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="group/[id]"
          options={{ headerShown: false, animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="group/recommendations"
          options={{ headerShown: false, animation: 'slide_from_right' }}
        />
      </Stack>
    </>
  );
}
