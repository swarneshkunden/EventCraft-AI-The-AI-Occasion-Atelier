/**
 * Authentication service and state manager.
 */
import { api } from './api.js';

let currentUser = null;
const listeners = new Set();

export function subscribeAuth(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify() {
  for (const fn of listeners) {
    try {
      fn(currentUser);
    } catch (e) {
      console.error('Auth listener error', e);
    }
  }
}

export function getCurrentUser() {
  return currentUser;
}

export async function checkSession() {
  try {
    const user = await api.get('/api/auth/me');
    currentUser = user;
    notify();
    return user;
  } catch (err) {
    currentUser = null;
    notify();
    return null;
  }
}

export async function login(email, password) {
  await api.post('/api/auth/login', { email, password });
  return await checkSession();
}

export async function signup(email, password, displayName, currency = 'USD') {
  return await api.post('/api/auth/signup', {
    email,
    password,
    display_name: displayName,
    currency,
  });
}

export async function logout() {
  try {
    await api.post('/api/auth/logout', {});
  } catch {
    // Ignore error on logout
  }
  currentUser = null;
  notify();
}

export async function loadDemo() {
  const data = await api.post('/api/demo/load', {});
  await checkSession();
  return data;
}
