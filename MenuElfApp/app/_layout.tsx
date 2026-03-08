import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, ActivityIndicator, View } from 'react-native';
import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import type { Session } from '@supabase/supabase-js';
import LoginScreen from './login';

export default function RootLayout() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s);
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });

    return () => subscription.unsubscribe();
  }, []);

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
