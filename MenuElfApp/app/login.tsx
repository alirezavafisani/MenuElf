import React, { useState, useRef, useEffect } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity,
  KeyboardAvoidingView, Platform, ScrollView, Keyboard,
  TouchableWithoutFeedback, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '../lib/supabase';
import { colors, radii, spacing } from '../lib/theme';
import GoldButton from '../components/ui/GoldButton';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, { toValue: 1, duration: 600, useNativeDriver: true }).start();
  }, []);

  const handleAuth = async () => {
    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }
    if (isSignUp && password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setError('');
    setLoading(true);

    const { error: err } = isSignUp
      ? await supabase.auth.signUp({ email: email.trim(), password: password.trim() })
      : await supabase.auth.signInWithPassword({ email: email.trim(), password: password.trim() });

    setLoading(false);
    if (err) setError(err.message);
  };

  return (
    <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
      <SafeAreaView style={styles.container}>
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
          >
            <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
              <View style={styles.header}>
                <Text style={styles.logoEmoji}>&#129399;</Text>
                <Text style={styles.title}>MenuElf</Text>
                <Text style={styles.subtitle}>Discover your perfect dish</Text>
              </View>

              <View style={styles.form}>
                <View style={[styles.inputContainer, emailFocused && styles.inputFocused]}>
                  <TextInput
                    style={styles.input}
                    placeholder="Email"
                    placeholderTextColor={colors.textTertiary}
                    value={email}
                    onChangeText={setEmail}
                    autoCapitalize="none"
                    keyboardType="email-address"
                    textContentType="emailAddress"
                    onFocus={() => setEmailFocused(true)}
                    onBlur={() => setEmailFocused(false)}
                  />
                </View>

                <View style={[styles.inputContainer, passwordFocused && styles.inputFocused]}>
                  <TextInput
                    style={[styles.input, { flex: 1 }]}
                    placeholder="Password"
                    placeholderTextColor={colors.textTertiary}
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry={!showPassword}
                    textContentType="password"
                    onFocus={() => setPasswordFocused(true)}
                    onBlur={() => setPasswordFocused(false)}
                  />
                  <TouchableOpacity onPress={() => setShowPassword(!showPassword)} style={styles.eyeBtn}>
                    <Text style={styles.eyeText}>{showPassword ? 'Hide' : 'Show'}</Text>
                  </TouchableOpacity>
                </View>

                {error ? <Text style={styles.errorText}>{error}</Text> : null}

                <GoldButton
                  title={isSignUp ? 'Create Account' : 'Sign In'}
                  onPress={handleAuth}
                  loading={loading}
                />

                <TouchableOpacity
                  style={styles.toggleBtn}
                  onPress={() => { setIsSignUp(!isSignUp); setError(''); }}
                >
                  <Text style={styles.toggleText}>
                    {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
                    <Text style={styles.toggleHighlight}>
                      {isSignUp ? 'Sign In' : 'Sign Up'}
                    </Text>
                  </Text>
                </TouchableOpacity>
              </View>
            </Animated.View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </TouchableWithoutFeedback>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 32,
    paddingBottom: 40,
  },
  content: { width: '100%' },
  header: {
    alignItems: 'center',
    marginBottom: 48,
  },
  logoEmoji: {
    fontSize: 48,
    marginBottom: 12,
  },
  title: {
    fontSize: 38,
    fontWeight: '900',
    color: colors.goldPrimary,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  form: {
    width: '100%',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.input,
    marginBottom: 16,
  },
  inputFocused: {
    borderColor: colors.goldPrimary,
  },
  input: {
    flex: 1,
    paddingHorizontal: 18,
    paddingVertical: 16,
    fontSize: 16,
    color: colors.textPrimary,
  },
  eyeBtn: {
    paddingHorizontal: 14,
    paddingVertical: 16,
  },
  eyeText: {
    color: colors.textTertiary,
    fontSize: 13,
    fontWeight: '600',
  },
  errorText: {
    color: colors.error,
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 16,
  },
  toggleBtn: {
    marginTop: 20,
    alignItems: 'center',
  },
  toggleText: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  toggleHighlight: {
    color: colors.goldPrimary,
    fontWeight: '600',
  },
});
