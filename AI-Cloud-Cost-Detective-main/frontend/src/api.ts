/**
 * API Client Utilities
 */

const API_BASE = 'http://localhost:8000/api';

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  code?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
}

export interface ResourceGroup {
  name: string;
}

export interface Resource {
  resource_type: string;
  name: string;
  region: string;
  sku: string;
  tags: Record<string, string>;
  arn: string;
}

export interface CostIssue {
  title: string;
  description: string;
  severity: 'high' | 'medium' | 'low';
  resource_name: string;
  resource_type: string;
  estimated_savings: string;
  fix_command?: string;
}

export interface CostAnalysis {
  summary: string;
  total_estimated_savings: string;
  issues: CostIssue[];
  recommendations: string[];
}

export interface AnalysisResponse {
  analysis_id: string;
  resource_group: string;
  resources: Resource[];
  total_resources: number;
  analysis?: CostAnalysis;
}

export interface AnalysisHistoryItem {
  id: number;
  resource_group: string;
  resources_scanned: number;
  issues_found: number;
  estimated_savings: string | null;
  status: string;
  created_at: string;
}

/**
 * Get authorization headers with JWT token
 */
function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const token = localStorage.getItem('access_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Signup API call
 */
export async function signup(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.error || 'Signup failed');
  }

  return response.json();
}

/**
 * Login API call
 */
export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.error || 'Login failed');
  }

  return response.json();
}

/**
 * Get list of AWS Resource Groups
 */
export async function getResourceGroups(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/resource-groups`, {
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.error || 'Failed to fetch resource groups');
  }

  const data = await response.json();
  return data.resource_groups || [];
}

/**
 * Get a specific analysis by database ID
 */
export async function getAnalysisById(analysisDbId: number): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE}/analysis/${analysisDbId}`, {
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.error || 'Failed to fetch analysis');
  }

  return response.json();
}

/**
 * Analyze a resource group
 */
export async function analyzeResourceGroup(resourceGroup: string): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ resource_group: resourceGroup }),
  });

  if (!response.ok) {
    // Try to surface backend structured error (detail.error) when available
    let errMsg = 'Analysis failed';
    try {
      const errorBody = await response.json();
      errMsg = errorBody?.detail?.error || errorBody?.error || JSON.stringify(errorBody);
    } catch (e) {
      try {
        errMsg = await response.text();
      } catch (_) {
        /* ignore */
      }
    }
    throw new Error(errMsg || 'Analysis failed');
  }

  return response.json();
}

/**
 * Get analysis history
 */
export async function getAnalysisHistory(): Promise<AnalysisHistoryItem[]> {
  const response = await fetch(`${API_BASE}/history`, {
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.error || 'Failed to fetch history');
  }

  const data = await response.json();
  return data.analyses || [];
}

/**
 * Connect to WebSocket for progress tracking
 */
export function connectToProgress(
  analysisId: string,
  onMessage: (message: { type: string; message: string; timestamp: string }) => void,
  onError: (error: Event) => void,
  onClose: (event: CloseEvent) => void
): WebSocket {
  const ws = new WebSocket(`ws://localhost:8000/ws/progress/${analysisId}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };

  ws.onerror = onError;
  ws.onclose = onClose;

  return ws;
}
