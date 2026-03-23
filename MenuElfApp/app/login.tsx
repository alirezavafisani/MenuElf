import React, { useState, useRef, useEffect } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity,
  KeyboardAvoidingView, Platform, ScrollView, Keyboard,
  TouchableWithoutFeedback, Animated, Linking,
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

  const isValidEmail = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);

  const friendlyError = (msg: string): string => {
    const lower = msg.toLowerCase();
    if (lower.includes('invalid_grant') || lower.includes('invalid login'))
      return 'Incorrect email or password. Please try again.';
    if (lower.includes('email not confirmed'))
      return 'Please check your inbox and confirm your email before signing in.';
    if (lower.includes('user already registered'))
      return 'An account with this email already exists. Try signing in instead.';
    if (lower.includes('rate limit') || lower.includes('too many'))
      return 'Too many attempts. Please wait a moment and try again.';
    if (lower.includes('network') || lower.includes('fetch'))
      return 'Network error. Please check your connection.';
    return msg;
  };

  const handleAuth = async () => {
    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }
    if (!isValidEmail(email.trim())) {
      setError('Please enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setError('');
    setLoading(true);

    try {
      const { error: err } = isSignUp
        ? await supabase.auth.signUp({ email: email.trim(), password: password.trim() })
        : await supabase.auth.signInWithPassword({ email: email.trim(), password: password.trim() });

      if (err) setError(friendlyError(err.message));
    } catch {
      setError('Something went wrong. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async () => {
    const trimmed = email.trim();
    if (!trimmed || !isValidEmail(trimmed)) {
      setError('Enter your email address above, then tap Forgot Password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(trimmed);
      if (err) {
        setError(friendlyError(err.message));
      } else {
        setError('');
        setPassword('');
        // Use a brief success message in the error field
        setError('Password reset email sent! Check your inbox.');
      }
    } catch {
      setError('Could not send reset email. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
      <SafeAreaView style={styles.container}>
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
            <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
              <View style={styles.header}>
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

                {isSignUp && (
                  <Text style={styles.passwordHint}>Minimum 6 characters</Text>
                )}

                {!isSignUp && (
                  <TouchableOpacity onPress={handleForgotPassword} style={styles.forgotBtn}>
                    <Text style={styles.forgotText}>Forgot Password?</Text>
                  </TouchableOpacity>
                )}

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

                <View style={styles.legalLinks}>
                  <TouchableOpacity onPress={() => Linking.openURL('https://menuelf-production.up.railway.app/legal/privacy')}>
                    <Text style={styles.legalText}>Privacy Policy</Text>
                  </TouchableOpacity>
                  <Text style={styles.legalDot}> · </Text>
                  <TouchableOpacity onPress={() => Linking.openURL('https://menuelf-production.up.railway.app/legal/terms')}>
                    <Text style={styles.legalText}>Terms of Service</Text>
                  </TouchableOpacity>
                </View>
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
  scrollContent: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 32, paddingBottom: 40 },
  content: { width: '100%' },
  header: { alignItems: 'center', marginBottom: 48 },
  title: { fontSize: 38, fontWeight: '900', color: colors.textPrimary, marginBottom: 8 },
  subtitle: { fontSize: 16, color: colors.textSecondary, fontWeight: '500' },
  form: { width: '100%' },
  inputContainer: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.backgroundTertiary,
    borderWidth: 1, borderColor: 'transparent',
    borderRadius: radii.input, marginBottom: 16,
  },
  inputFocused: { borderColor: colors.borderFocus },
  input: { flex: 1, paddingHorizontal: 18, paddingVertical: 16, fontSize: 16, color: colors.textPrimary },
  eyeBtn: { paddingHorizontal: 14, paddingVertical: 16 },
  eyeText: { color: colors.textTertiary, fontSize: 13, fontWeight: '600' },
  passwordHint: { color: colors.textTertiary, fontSize: 12, marginBottom: 12, marginLeft: 4 },
  forgotBtn: { alignSelf: 'flex-end', marginBottom: 12 },
  forgotText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  errorText: { color: colors.error, fontSize: 14, textAlign: 'center', marginBottom: 16 },
  toggleBtn: { marginTop: 20, alignItems: 'center' },
  toggleText: { color: colors.textSecondary, fontSize: 14 },
  toggleHighlight: { color: colors.accent, fontWeight: '600' },
  legalLinks: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 32 },
  legalText: { color: colors.textTertiary, fontSize: 12 },
  legalDot: { color: colors.textTertiary, fontSize: 12 },
});
