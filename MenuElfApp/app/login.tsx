import React, { useState, useRef, useEffect } from 'react';
import {
  StyleSheet, View, Text, TextInput, TouchableOpacity,
  KeyboardAvoidingView, Platform, ScrollView, Keyboard,
  TouchableWithoutFeedback, Animated, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import * as WebBrowser from 'expo-web-browser';
import * as AuthSession from 'expo-auth-session';
import { Ionicons } from '@expo/vector-icons';
import { supabase } from '../lib/supabase';
import { colors, radii } from '../lib/theme';
import GoldButton from '../components/ui/GoldButton';

const privacyPolicyHtml = require('../assets/privacy-policy.html');
const termsOfServiceHtml = require('../assets/terms-of-service.html');

WebBrowser.maybeCompleteAuthSession();

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [legalType, setLegalType] = useState<'privacy' | 'terms' | null>(null);
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
    if (lower.includes('rate limit') || lower.includes('too many') || lower.includes('after') && lower.includes('seconds'))
      return 'Please wait a moment before trying again.';
    if (lower.includes('network') || lower.includes('fetch'))
      return 'Network error. Please check your connection.';
    if (lower.includes('provider is not enabled') || lower.includes('unsupported provider'))
      return 'Google Sign In is being set up. Please use email for now.';
    return msg;
  };

  const signInWithGoogle = async () => {
    setError('');
    setSuccessMsg('');
    setGoogleLoading(true);
    try {
      const redirectUri = AuthSession.makeRedirectUri({ scheme: 'menuelfapp' });
      const { data, error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: redirectUri },
      });

      if (oauthError) {
        setError(friendlyError(oauthError.message));
        return;
      }

      if (data?.url) {
        const result = await WebBrowser.openAuthSessionAsync(data.url, redirectUri);
        if (result.type === 'success' && result.url) {
          const url = new URL(result.url);
          // Tokens can be in hash fragment or query params
          const hashParams = new URLSearchParams(url.hash.substring(1));
          const queryParams = new URLSearchParams(url.search);
          const access_token = hashParams.get('access_token') || queryParams.get('access_token');
          const refresh_token = hashParams.get('refresh_token') || queryParams.get('refresh_token');
          if (access_token && refresh_token) {
            await supabase.auth.setSession({ access_token, refresh_token });
          }
        }
      }
    } catch {
      setError('Google Sign In is being set up. Please use email for now.');
    } finally {
      setGoogleLoading(false);
    }
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
    setSuccessMsg('');
    setLoading(true);

    try {
      if (isSignUp) {
        const { data, error: err } = await supabase.auth.signUp({
          email: email.trim(),
          password: password.trim(),
        });

        if (err) {
          setError(friendlyError(err.message));
        } else if (data.user) {
          if (data.session) {
            // Auto-confirmed, session is active — _layout.tsx will handle navigation
          } else {
            // No session yet — try signing in directly (works if email confirm is off)
            const { data: signInData, error: signInError } = await supabase.auth.signInWithPassword({
              email: email.trim(),
              password: password.trim(),
            });
            if (signInData?.session) {
              // Signed in — _layout.tsx will handle navigation
            } else if (signInError) {
              // Can't auto-sign-in; show a friendly message and switch to sign-in mode
              setSuccessMsg('Account created! You can sign in now.');
              setIsSignUp(false);
            }
          }
        }
      } else {
        const { error: err } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password: password.trim(),
        });
        if (err) setError(friendlyError(err.message));
      }
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
    setSuccessMsg('');
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(trimmed);
      if (err) {
        setError(friendlyError(err.message));
      } else {
        setPassword('');
        setSuccessMsg('Password reset link sent to your email.');
      }
    } catch {
      setError('Could not send reset email. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Legal overlay
  if (legalType) {
    const isPrivacy = legalType === 'privacy';
    const title = isPrivacy ? 'Privacy Policy' : 'Terms of Service';
    const source = isPrivacy ? privacyPolicyHtml : termsOfServiceHtml;

    return (
      <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
        <View style={styles.legalHeader}>
          <TouchableOpacity onPress={() => setLegalType(null)} style={styles.legalBackBtn}>
            <Ionicons name="chevron-back" size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.legalTitle}>{title}</Text>
          <View style={styles.legalSpacer} />
        </View>
        <WebView
          source={source}
          style={styles.legalWebview}
          originWhitelist={['*']}
        />
      </SafeAreaView>
    );
  }

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
                {/* Google Sign In */}
                <TouchableOpacity
                  style={styles.googleBtn}
                  onPress={signInWithGoogle}
                  disabled={googleLoading || loading}
                  activeOpacity={0.7}
                >
                  <Text style={styles.googleIcon}>G</Text>
                  <Text style={styles.googleText}>
                    {googleLoading ? 'Signing in…' : 'Continue with Google'}
                  </Text>
                </TouchableOpacity>

                {/* Separator */}
                <View style={styles.separator}>
                  <View style={styles.separatorLine} />
                  <Text style={styles.separatorText}>or</Text>
                  <View style={styles.separatorLine} />
                </View>

                {/* Email input */}
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

                {/* Password input */}
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
                {successMsg ? <Text style={styles.successText}>{successMsg}</Text> : null}

                <GoldButton
                  title={isSignUp ? 'Create Account' : 'Sign In'}
                  onPress={handleAuth}
                  loading={loading}
                />

                <TouchableOpacity
                  style={styles.toggleBtn}
                  onPress={() => { setIsSignUp(!isSignUp); setError(''); setSuccessMsg(''); }}
                >
                  <Text style={styles.toggleText}>
                    {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
                    <Text style={styles.toggleHighlight}>
                      {isSignUp ? 'Sign In' : 'Sign Up'}
                    </Text>
                  </Text>
                </TouchableOpacity>

                <View style={styles.legalLinks}>
                  <TouchableOpacity onPress={() => setLegalType('privacy')}>
                    <Text style={styles.legalText}>Privacy Policy</Text>
                  </TouchableOpacity>
                  <Text style={styles.legalDot}> · </Text>
                  <TouchableOpacity onPress={() => setLegalType('terms')}>
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

  // Google button
  googleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.button,
    paddingVertical: 14,
    marginBottom: 20,
  },
  googleIcon: {
    fontSize: 18,
    fontWeight: '700',
    color: '#4285F4',
    marginRight: 10,
  },
  googleText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
  },

  // Separator
  separator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  separatorLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  separatorText: {
    paddingHorizontal: 16,
    fontSize: 13,
    color: colors.textTertiary,
    fontWeight: '500',
  },

  // Inputs
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
  successText: { color: colors.success, fontSize: 14, textAlign: 'center', marginBottom: 16 },
  toggleBtn: { marginTop: 20, alignItems: 'center' },
  toggleText: { color: colors.textSecondary, fontSize: 14 },
  toggleHighlight: { color: colors.accent, fontWeight: '600' },
  legalLinks: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 32 },
  legalText: { color: colors.textTertiary, fontSize: 12 },
  legalDot: { color: colors.textTertiary, fontSize: 12 },

  // Legal overlay
  legalHeader: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  legalBackBtn: { padding: 4, marginRight: 8 },
  legalTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  legalSpacer: { width: 36 },
  legalWebview: { flex: 1, backgroundColor: colors.background },
});
