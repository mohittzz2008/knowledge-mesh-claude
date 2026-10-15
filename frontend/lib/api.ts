/** API Client & Typed Adapter Architecture for Knowledge Mesh & Intelligent Recommendations */

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

type ClerkLike = {
  session?: { getToken?: () => Promise<string | null>; user?: { id: string } };
};

/**
 * Auth headers for every backend call. With Clerk configured on the backend (CLERK_JWKS_URL)
 * the signed session token in `Authorization` is what authenticates the request; the
 * `X-Clerk-User-Id` header is only honoured by the backend in local dev mode.
 */
async function getAuthHeaders(customHeaders: Record<string, string> = {}): Promise<Record<string, string>> {
  const headers: Record<string, string> = { ...customHeaders };
  if (typeof window !== 'undefined') {
    const clerk = (window as unknown as { Clerk?: ClerkLike }).Clerk;
    const session = clerk?.session;
    if (session?.getToken) {
      try {
        const token = await session.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;
      } catch {
        /* fall through to the dev header */
      }
    }
    if (session?.user?.id) {
      headers['X-Clerk-User-Id'] = session.user.id;
    } else {
      // No active Clerk session.  In local development the backend accepts
      // a fixed user-id header (ALLOW_INSECURE_DEV_AUTH=true).  Only inject
      // this when the env var is explicitly set; in production it should be
      // left unset so the backend rejects unauthenticated requests normally.
      const devId = process.env.NEXT_PUBLIC_DEV_USER_ID;
      if (devId) headers['X-Clerk-User-Id'] = devId;
    }
  }
  return headers;
}

export interface HealthCheckResponse {
  status: string;
  service?: string;
  database?: string;
}

export interface PlatformConnectPayload {
  platform: string;
  authType: 'username_public' | 'oauth_token';
  identifier: string; // username or auth code
}

export interface PlatformRegistryItem {
  key: string;
  name: string;
  capabilities: string[];
  status: string; // 'AVAILABLE' | 'OAUTH_REQUIRED' | 'LIMITED' | 'PLANNED' | 'UNSUPPORTED'
  auth_type: string;
  data_scope_description: string;
  documentation_url?: string;
  connected: boolean;
  connected_username?: string;
  last_synced_at?: string | null;
}

export interface UserProfileResponse {
  user_id: string;
  developer_name: string;
  overall_skill_score: number;
  total_evidence_count: number;
  external_evidence_count: number;
  codelab_artifacts_count: number;
  code_artifacts_count: number;
  connected_platforms: Array<{
    platform: string;
    connected: boolean;
    username?: string;
    last_synced_at?: string;
  }>;
  platform_counts: Record<string, number>;
  skills: Array<{
    skill_name: string;
    slug: string;
    category: string;
    mastery: number;
    status: string;
    evidence_count: number;
    sources?: Record<string, number>;
  }>;
  next_best_action?: Record<string, unknown>;
}

export interface GitHubValidateResponse {
  platform: string;
  username: string;
  valid: boolean;
  total_solved?: number;
  avatar_url?: string;
  bio?: string;
  public_repos?: number;
  followers?: number;
  detail?: string;
}

export interface PlatformSyncResponse {
  platform_connection_id: string;
  platform: string;
  username: string;
  connected: boolean;
  synced_evidence_count: number;
  updated_evidence_count?: number;
  profile_summary: {
    highlights?: Array<{ label: string; value: string | number }>;
    public_repos?: number;
    total_solved?: number;
    followers?: number;
    avatar_url?: string;
    html_url?: string;
    bio?: string;
  };
  last_synced_at: string;
  message: string;
}

/** @deprecated use PlatformSyncResponse */
export type GitHubSyncResponse = PlatformSyncResponse;

export interface EvidenceItemResponse {
  id: string;
  user_id: string;
  platform_connection_id: string;
  external_id?: string;
  title: string;
  evidence_type: string;
  raw_payload?: Record<string, unknown>;
  normalized_payload?: {
    repository_name?: string;
    full_name?: string;
    primary_language?: string;
    skills?: string[];
    stars?: number;
    description?: string;
    event_type?: string;
  };
  occurred_at?: string;
  created_at: string;
}

export interface EvidenceListResponse {
  items: EvidenceItemResponse[];
  total: number;
  platform_counts: Record<string, number>;
}

export interface CodeAnalysisResponse {
  id: string;
  code_artifact_id: string;
  language: string;
  lines_of_code: number;
  function_count: number;
  class_count: number;
  cyclomatic_complexity: number;
  has_recursion: boolean;
  detected_concepts?: string[];
  data_structures?: string[];
  analysis_summary?: {
    imports?: string[];
    function_names?: string[];
    class_names?: string[];
    valid_syntax?: boolean;
    error_detail?: string;
  };
  created_at: string;
}

export interface CodeArtifactResponse {
  id: string;
  user_id: string;
  platform_connection_id: string;
  platform: string;
  repository: string;
  file_path: string;
  source_url?: string;
  commit_sha?: string;
  language: string;
  code_content: string;
  size_bytes: number;
  created_at: string;
  analysis?: CodeAnalysisResponse;
}

export interface CodeArtifactListResponse {
  items: CodeArtifactResponse[];
  total: number;
}

export interface CodeArtifactLinkSchema {
  id: string;
  repository: string;
  file_path: string;
  language: string;
  source_url?: string;
  lines_of_code: number;
  has_recursion: boolean;
  created_at?: string;
}

export interface KnowledgeMeshNodeData {
  skill_id: string;
  name: string;
  slug: string;
  category: string;
  mastery: number;
  status: string; // 'mastered' | 'developing' | 'weak' | 'insufficient'
  evidenceCount: number;
  evidenceStrength: string; // 'Strong' | 'Moderate' | 'Limited' | 'None'
  confidence: number;
  description?: string;
  sources: string[];
  linkedArtifacts: CodeArtifactLinkSchema[];
  explanation: string;
  recentActivity: string;
  recommendation: string;
}

export interface KnowledgeMeshNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: KnowledgeMeshNodeData;
}

export interface KnowledgeMeshEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  animated: boolean;
  style?: Record<string, unknown>;
}

export interface KnowledgeMeshResponse {
  user_id: string;
  nodes: KnowledgeMeshNode[];
  edges: KnowledgeMeshEdge[];
  total_skills: number;
  assessed_skills_count: number;
}

export interface NextBestActionResponse {
  target_skill: string;
  slug: string;
  reason: string;
  evidence_count: number;
  recommended_difficulty: string;
  learning_objective: string;
  prerequisites: string[];
  has_sufficient_evidence: boolean;
}

export interface PracticeRecommendation {
  problem_id: string;
  platform: string;
  title: string;
  url?: string;
  difficulty: string;
  target_difficulty?: string;
  topics: string[];
  target_skill_slug: string;
  reason: string;
  source: string;
  status_label: string;
  is_real_data: boolean;
}

export interface PracticeRecommendationListResponse {
  recommendations: PracticeRecommendation[];
  total: number;
}

export interface LearningPathStep {
  id: string;
  step_number: number;
  title: string;
  slug: string;
  category: string;
  status: 'completed' | 'in_progress' | 'recommended' | 'locked';
  mastery: number;
  evidence_count: number;
  why: string;
  prerequisites: string[];
  recommended_practice: string;
}

export interface LearningPathResponse {
  user_id: string;
  target_goal: string;
  current_focus_skill: string;
  steps: LearningPathStep[];
  total_steps: number;
}

export interface EvidenceReference {
  title: string;
  platform: string;
  repository?: string;
  file_path?: string;
  source_url?: string;
}

export interface SuggestedAction {
  label: string;
  action_type: string;
  target_path: string;
  target_id?: string;
}

export interface CoachMessageResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  intent?: string;
  confidence?: number;
  context_used?: Record<string, unknown>;
  evidence_references: EvidenceReference[];
  suggested_actions: SuggestedAction[];
  detected_mistake_patterns?: Array<Record<string, unknown>>;
  created_at: string;
}

export interface CoachMessageItem {
  id: string;
  sender: 'user' | 'ai';
  content: string;
  intent?: string;
  confidence?: number;
  context_used?: Record<string, unknown>;
  evidence_references: EvidenceReference[];
  suggested_actions: SuggestedAction[];
  detected_mistake_patterns?: Array<Record<string, unknown>>;
  created_at?: string;
}

export interface CoachConversation {
  id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  message_count: number;
}

export interface TestCaseResult {
  test_case: number;
  passed: boolean;
  actual: string;
  expected: string;
  error?: string;
}

export interface CodeRunResponse {
  status: string;
  stdout: string;
  stderr: string;
  execution_time_ms: number;
  passed_count: number;
  total_tests: number;
  test_results: TestCaseResult[];
  error_message?: string;
}

export interface CodeAnalyzeResponse {
  valid_syntax: boolean;
  ast_metrics: Record<string, unknown>;
  diagnostic_report: string;
  original_code: string;
  suggested_code: string;
  explanation: string;
}

export interface CodeSubmitResponse {
  attempt_id: string;
  status: string;
  is_passed: boolean;
  execution_time_ms: number;
  passed_count: number;
  total_tests: number;
  diagnostic_report: string;
  telemetry_logged: boolean;
  evidence_id: string;
  message: string;
}

export interface CodeHintResponse {
  problem_id: string;
  hint_level: number;
  total_hints: number;
  hint: string;
}

export interface CodeLabProblemDetail {
  id: string;
  title: string;
  slug: string;
  difficulty: string;
  target_skill: string;
  learning_objective: string;
  description: string;
  initial_code: string;
  suggested_code: string;
  test_cases: Array<{
    input: string;
    function_call: string;
    expected: string;
  }>;
  hints: string[];
}

export async function fetchHealth(): Promise<HealthCheckResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDbHealth(): Promise<HealthCheckResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/db-health`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchUserProfile(): Promise<UserProfileResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/user/profile`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching user profile:', err);
    return null;
  }
}

export async function fetchPlatformRegistry(): Promise<PlatformRegistryItem[] | { error: string }> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/platforms`, {
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) {
      let detail = `Server returned ${res.status}`;
      if (res.status === 401) detail = 'Not authenticated (401). Backend dev-auth may not be enabled.';
      else if (res.status === 403) detail = 'Forbidden (403). Check ALLOW_INSECURE_DEV_AUTH in backend/.env.';
      else if (res.status === 503) detail = 'Backend unavailable (503). Is the server running?';
      try {
        const body = await res.json();
        if (body?.detail) detail = body.detail;
      } catch { /* ignore */ }
      console.error('[API Client] fetchPlatformRegistry failed:', detail);
      return { error: detail };
    }
    return await res.json();
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Could not reach the backend.';
    console.error('[API Client] fetchPlatformRegistry network error:', msg);
    return { error: `Network error: ${msg}` };
  }
}

export async function validatePlatformUser(platformKey: string, username: string): Promise<GitHubValidateResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/platforms/${encodeURIComponent(platformKey)}/validate`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ username }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: `Server error ${res.status}` }));
      return { platform: platformKey, username, valid: false, detail: errData.detail };
    }
    return await res.json();
  } catch (err) {
    console.error(`[API Client] Error validating ${platformKey} user:`, err);
    return null;
  }
}

export async function syncPlatformUser(
  platformKey: string,
  username: string,
  authType = 'username_public',
  authToken?: string
): Promise<PlatformSyncResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/platforms/${encodeURIComponent(platformKey)}/sync`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        username,
        auth_type: authType,
        auth_token: authToken,
      }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Unknown server error' }));
      throw new Error(errData.detail || `Server error ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`[API Client] Error syncing ${platformKey} user:`, err);
    throw err;
  }
}

export async function disconnectPlatformUser(platformKey: string): Promise<{message: string} | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/platforms/${encodeURIComponent(platformKey)}/disconnect`, {
      method: 'POST',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Unknown server error' }));
      throw new Error(errData.detail || `Server error ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`[API Client] Error disconnecting ${platformKey}:`, err);
    throw err;
  }
}

export async function validateGitHubUser(username: string): Promise<GitHubValidateResponse | null> {
  return validatePlatformUser('github', username);
}

export async function syncGitHubUser(
  username: string,
  authType = 'username_public',
  authToken?: string
): Promise<PlatformSyncResponse | null> {
  return syncPlatformUser('github', username, authType, authToken);
}

export async function fetchEvidenceList(platform?: string): Promise<EvidenceListResponse | null> {
  try {
    const query = platform ? `?platform=${encodeURIComponent(platform)}` : '';
    const res = await fetch(`${BACKEND_URL}/api/v1/evidence${query}`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching evidence items:', err);
    return null;
  }
}

export async function fetchCodeArtifacts(): Promise<CodeArtifactListResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/code-artifacts`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching code artifacts:', err);
    return null;
  }
}

export async function analyzeGitHubFile(
  owner: string,
  repo: string,
  path: string,
  authToken?: string
): Promise<CodeArtifactResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/code-artifacts/analyze-github-file`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        owner,
        repo,
        path,
        auth_token: authToken,
      }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Failed to analyze GitHub file' }));
      throw new Error(errData.detail || `Server error ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error analyzing GitHub file:', err);
    throw err;
  }
}

export async function fetchKnowledgeMesh(): Promise<KnowledgeMeshResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/knowledge-mesh`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching Knowledge Mesh graph:', err);
    return null;
  }
}

export async function fetchNextBestAction(): Promise<NextBestActionResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/next-best-action`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching Next Best Action:', err);
    return null;
  }
}

export async function fetchPracticeRecommendations(
  skill = 'recursion',
  platform?: string,
  difficulty?: string
): Promise<PracticeRecommendationListResponse | null> {
  try {
    const params = new URLSearchParams({ skill });
    if (platform) params.append('platform', platform);
    if (difficulty) params.append('difficulty', difficulty);

    const res = await fetch(`${BACKEND_URL}/api/v1/recommendations?${params.toString()}`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching practice recommendations:', err);
    return null;
  }
}

export async function fetchLearningPath(): Promise<LearningPathResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/learning-path`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching learning path:', err);
    return null;
  }
}

export async function sendCoachMessage(
  message: string,
  conversationId?: string,
  codeArtifactId?: string
): Promise<CoachMessageResponse> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/api/v1/coach/messages`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        code_artifact_id: codeArtifactId,
      }),
    });
  } catch (err) {
    console.error('[API Client] Error sending coach message:', err);
    throw new Error('Could not reach the server. Check that the backend is running and try again.');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const raw = body && typeof body.detail === 'string' ? body.detail : '';
    let fallback = `The coach could not answer (error ${res.status}).`;
    if (res.status === 503) fallback = 'The coach is not set up on this server yet. An AI provider needs to be configured.';
    else if (res.status === 502) fallback = 'The AI provider failed to respond. Try again in a moment.';
    throw new Error(raw || fallback);
  }
  return await res.json();
}

export async function fetchCoachConversations(): Promise<CoachConversation[] | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/coach/conversations`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching coach conversations:', err);
    return null;
  }
}

export async function fetchCodeLabProblem(problemId: string): Promise<CodeLabProblemDetail | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/code-lab/problems/${encodeURIComponent(problemId)}`, { 
      cache: 'no-store',
      headers: await getAuthHeaders(),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching Code Lab problem:', err);
    return null;
  }
}

export async function runCodeLab(code: string, language = 'Python', problemId = 'problem-tree-inorder'): Promise<CodeRunResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/code-lab/run`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ code, language, problem_id: problemId }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error running Code Lab test cases:', err);
    return null;
  }
}

export async function analyzeCodeLab(code: string, language = 'Python', problemId = 'problem-tree-inorder'): Promise<CodeAnalyzeResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/code-lab/analyze`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ code, language, problem_id: problemId }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error analyzing Code Lab logic:', err);
    return null;
  }
}

export async function submitCodeLab(code: string, language = 'Python', problemId = 'problem-tree-inorder'): Promise<CodeSubmitResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/code-lab/submit`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ code, language, problem_id: problemId }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error submitting Code Lab solution:', err);
    return null;
  }
}

export async function fetchCodeLabHint(problemId = 'problem-tree-inorder', hintLevel = 1): Promise<CodeHintResponse | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/code-lab/hint`, {
      method: 'POST',
      headers: await getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ problem_id: problemId, hint_level: hintLevel }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('[API Client] Error fetching Code Lab hint:', err);
    return null;
  }
}
