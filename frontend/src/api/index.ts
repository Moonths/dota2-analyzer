const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
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
}

export interface ProviderItem {
  id: string
  name: string
  models: string[]
}

export const api = {
  getPlayer: (id: number) => request<PlayerInfo>(`/players/${id}`),
  getPlayerMatches: (id: number, limit = 20) =>
    request<PlayerMatches>(`/players/${id}/matches?limit=${limit}`),
  getMatchInfo: (id: number) => request<any>(`/matches/${id}`),
  analyze: (matchId: number, provider?: string, model?: string) =>
    request<AnalysisResult>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ match_id: matchId, provider, model }),
    }),
  getProviders: () => request<{ providers: ProviderItem[] }>('/providers'),
  getSharedAnalysis: (shareId: string) =>
    request<AnalysisResult>(`/share/${shareId}`),
}
