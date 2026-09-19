import {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  OverviewMetrics,
  QualityMetrics,
} from './types';

// API base URL is configurable through VITE_API_BASE_URL (defaults to empty string for relative proxy/same-origin)
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export async function sendChatMessage(
  message: string,
  history: Array<{ role: string; content: string }> = []
): Promise<ChatResponse> {
  const url = `${API_BASE_URL}/api/chat`;
  const payload: ChatRequest = {
    message,
    history: history.length > 0 ? history : undefined,
  };

  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    let errorDetail = `Request failed with status ${resp.status}`;
    try {
      const errData = await resp.json();
      if (errData.detail) {
        errorDetail = errData.detail;
      }
    } catch {
      // Ignore JSON parse errors on non-200 responses
    }
    throw new Error(errorDetail);
  }

  return (await resp.json()) as ChatResponse;
}

export async function checkHealth(): Promise<HealthResponse> {
  const url = `${API_BASE_URL}/health`;
  const resp = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!resp.ok) {
    throw new Error(`Health check failed with status ${resp.status}`);
  }

  return (await resp.json()) as HealthResponse;
}

export async function fetchOverviewMetrics(): Promise<OverviewMetrics> {
  const url = `${API_BASE_URL}/api/overview`;
  const resp = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!resp.ok) {
    throw new Error(`Failed to fetch overview metrics: ${resp.status}`);
  }

  return (await resp.json()) as OverviewMetrics;
}

export async function fetchQualityMetrics(): Promise<QualityMetrics> {
  const url = `${API_BASE_URL}/api/quality`;
  const resp = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!resp.ok) {
    throw new Error(`Failed to fetch quality metrics: ${resp.status}`);
  }

  return (await resp.json()) as QualityMetrics;
}
