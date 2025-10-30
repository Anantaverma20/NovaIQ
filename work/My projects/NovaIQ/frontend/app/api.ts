/**
 * API client for NovaIQ backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

async function apiFetch(endpoint: string, options?: RequestInit) {
  const url = `${API_BASE}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export async function fetchInsights(limit = 20, offset = 0) {
  return apiFetch(`/insights?limit=${limit}&offset=${offset}`);
}

export async function fetchHypotheses(insightId?: number) {
  const query = insightId ? `?insight_id=${insightId}` : '';
  return apiFetch(`/hypotheses${query}`);
}

export async function triggerIngestion() {
  return apiFetch('/ingest/run', { method: 'POST' });
}

export async function askQuestion(question: string) {
  return apiFetch('/ask', {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

