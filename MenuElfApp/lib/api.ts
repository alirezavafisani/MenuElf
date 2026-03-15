import { supabase } from './supabase';
import { API_URL } from './config';

// Central API helper that always includes the user ID header
export async function apiCall(endpoint: string, options: RequestInit = {}) {
  const { data: { session } } = await supabase.auth.getSession();
  const userId = session?.user?.id;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (userId) {
    headers['x-user-id'] = userId;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  return response;
}

export async function apiGet(endpoint: string) {
  return apiCall(endpoint, { method: 'GET' });
}

export async function apiPost(endpoint: string, body: any) {
  return apiCall(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function apiDelete(endpoint: string) {
  return apiCall(endpoint, { method: 'DELETE' });
}

// Log an interaction (fire and forget, don't block UI)
export function logInteraction(type: string, payload: Record<string, any>) {
  apiPost('/interactions/log', { interaction_type: type, payload }).catch(() => {});
}
