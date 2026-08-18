const BASE = '/api'
const CLIENT_ID_KEY = 'dota2_client_id'
const ANALYSIS_CACHE_PREFIX = 'dota2_analysis_cache_'

function getClientId(): string {
  const saved = localStorage.getItem(CLIENT_ID_KEY)
  if (saved) return saved
  const generated = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `web_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
  localStorage.setItem(CLIENT_ID_KEY, generated)
  return generated
}

async function request<T>(
  url: string,
  options: RequestInit & { timeout?: number } = {},
): Promise<T> {
  const { timeout = 120000, ...fetchOptions } = options
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeout)

  try {
    const res = await fetch(`${BASE}${url}`, {
      headers: { 'Content-Type': 'application/json' },
      ...fetchOptions,
      signal: controller.signal,
    })
    if (!res.ok) {
      const err = await res.text()
      throw new Error(err || `HTTP ${res.status}`)
    }
    return res.json()
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('请求超时，请稍后重试')
    }
    throw error
  } finally {
    window.clearTimeout(timer)
  }
}

export interface PlayerInfo {
  profile: {
    account_id: number
    personaname: string
    avatarfull: string
  }
}

export interface MatchItem {
  match_id: number
  hero_name: string
  hero_icon: string
  kills: number
  deaths: number
  assists: number
  is_win: boolean
  duration: number
  start_time: number
  skill: string | null
}

export interface PlayerMatches {
  player_name: string
  matches: MatchItem[]
}

export interface PositionEval {
  position: number
  position_name: string
  player_name: string
  is_radiant: boolean
  hero_name: string
  is_qualified: boolean
  score: number
  summary: string
  highlights: string[]
  improvements: string[]
}

export interface PlayerCard {
  player_name: string
  hero_name: string
  hero_icon: string
  position: number
  is_radiant: boolean
  kda: string
  gpm: number
  xpm: number
  net_worth: number
  last_hits: number
  hero_damage: number
  tower_damage: number
  obs_placed: number
  sen_placed: number
  is_winner: boolean
  account_id: number
}

export interface TimelineEvent {
  time: number
  event_type: string
  description: string
  importance: string
}

export interface AnalysisResult {
  share_id: string
  match_id: number
  provider: string
  model: string
  mvp: PlayerCard & { reason: string }
  scapegoat: PlayerCard & { reason: string }
  position_evals: PositionEval[]
  timeline: TimelineEvent[]
  player_cards: PlayerCard[]
  game_summary: string
  radiant_win: boolean
  duration: number
  skill_level: string
  avg_mmr: number | null
  share_url: string
  radiant_players: PlayerCard[]
  dire_players: PlayerCard[]
  cached?: boolean
  quota_deducted?: boolean
  cache_source?: string
  message?: string
}

export interface ProviderItem {
  id: string
  name: string
  models: string[]
}

export interface Quota {
  limit: number
  used: number
  remaining: number
  analysis_limit?: number
  analysis_remaining?: number
  smurf_limit?: number
  smurf_remaining?: number
}

export interface SmurfSignal {
  label: string
  value: string
  detail: string
  score: number
}

export interface SmurfResult {
  player_id: number
  player_name: string
  score: number
  confidence: 'high' | 'medium' | 'low'
  signals: SmurfSignal[]
  roast: string
  details: Record<string, number>
  cached?: boolean
  quota_deducted?: boolean
  cache_source?: string
  message?: string
}

export function getCachedAnalysisLocal(matchId: number): AnalysisResult | null {
  try {
    const raw = localStorage.getItem(`${ANALYSIS_CACHE_PREFIX}${matchId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw) as AnalysisResult
    return parsed?.share_id ? parsed : null
  } catch {
    return null
  }
}

export function setCachedAnalysisLocal(matchId: number, result: AnalysisResult): void {
  try {
    localStorage.setItem(`${ANALYSIS_CACHE_PREFIX}${matchId}`, JSON.stringify(result))
  } catch {}
}

export const api = {
  getPlayer: (id: number) => request<PlayerInfo>(`/players/${id}`),
  getPlayerMatches: (id: number, limit = 20) =>
    request<PlayerMatches>(`/players/${id}/matches?limit=${limit}`),
  getMatchInfo: (id: number) => request<any>(`/matches/${id}`),
  analyze: (matchId: number, provider?: string, model?: string) =>
    request<AnalysisResult>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ match_id: matchId, provider, model, openid: getClientId() }),
    }),
  getCachedAnalysis: (matchId: number) =>
    request<AnalysisResult>(`/analysis/${matchId}/cache`),
  getProviders: () => request<{ providers: ProviderItem[] }>('/providers'),
  getQuota: () => request<Quota>(`/quota?openid=${encodeURIComponent(getClientId())}`),
  getSharedAnalysis: (shareId: string) =>
    request<AnalysisResult>(`/share/${shareId}`),
  getCachedSmurf: (playerId: number) =>
    request<SmurfResult>(`/smurf-check/${playerId}/cache`),
  smurfCheck: (playerId: number) =>
    request<SmurfResult>(`/smurf-check/${playerId}?openid=${encodeURIComponent(getClientId())}`, { timeout: 60000 }),
}
