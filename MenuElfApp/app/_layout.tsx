import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, ActivityIndicator, View } from 'react-native';
import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { supabase } from '../lib/supabase';
import { apiGet } from '../lib/api';
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
      // Reset onboarding check when user changes
      if (s?.user?.id) {
        checkOnboarding(s);
      } else {
        setOnboardingDone(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // Check onboarding when session is first established
  useEffect(() => {
    if (session) {
      checkOnboarding(session);
    }
  }, [session]);

  const checkOnboarding = async (sess: Session) => {
    // Check local cache first
    const cachedKey = `${ONBOARDING_KEY}_${sess.user.id}`;
    const cached = await AsyncStorage.getItem(cachedKey);
    if (cached === 'true') {
      setOnboardingDone(true);
      return;
    }

    // Check backend
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
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FBF7F4' }}>
        <ActivityIndicator size="large" color="#D4754E" />
      </View>
    );
  }

  if (!session) {
    return (
      <>
        <StatusBar style={Platform.OS === 'ios' ? 'dark' : 'auto'} />
        <LoginScreen />
      </>
    );
  }

  // Waiting for onboarding check
  if (onboardingDone === null) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FBF7F4' }}>
        <ActivityIndicator size="large" color="#D4754E" />
      </View>
    );
  }

  // Show onboarding if not completed
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
      <StatusBar style={Platform.OS === 'ios' ? 'dark' : 'auto'} />
      <Stack screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: '#FBF7F4' }
      }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="chat"
          options={{
            headerShown: false,
            presentation: 'modal',
            animation: 'slide_from_bottom'
          }}
        />
      </Stack>
    </>
  );
}
