import { ensureLogin, getOpenid } from '../utils/auth.js'

const ANALYSIS_CACHE_PREFIX = 'dota2_analysis_cache_'

// 根据运行环境选择 API 基地址
const BASE = (function() {
  // #ifdef H5
  return '/dota-api'
  // #endif
  // #ifndef H5
  return __API_BASE__
  // #endif
})()

function request(url, options = {}) {
  const timeout = options.timeout || 120000
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE + url,
      method: options.method || 'GET',
      data: options.body ? JSON.parse(options.body) : undefined,
      header: { 'Content-Type': 'application/json' },
      timeout,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const err = typeof res.data === 'string' ? res.data : JSON.stringify(res.data)
          reject(new Error(err || `HTTP ${res.statusCode}`))
        }
      },
      fail(err) {
        const msg = err.errMsg || err.message || 'Network error'
        if (msg.includes('url not in domain list') || msg.includes('合法域名')) {
          reject(new Error('请求域名未配置，请在小程序后台添加服务器域名'))
        } else if (msg.includes('timeout') || msg.includes('超时')) {
          reject(new Error('请求超时，请稍后重试'))
        } else {
          reject(new Error(msg))
        }
      },
    })
  })
}

export const api = {
  getPlayer(id) {
    return request(`/players/${id}`)
  },
  getPlayerMatches(id, limit = 20) {
    return request(`/players/${id}/matches?limit=${limit}`)
  },
  getMatchInfo(id) {
    return request(`/matches/${id}`)
  },
  getCachedAnalysis(matchId) {
    return request(`/analysis/${matchId}/cache`)
  },
  async analyze(matchId, provider, model) {
    await ensureLogin()
    // 后端可能需要等 OpenDota 解析 replay (最长 ~40s) 再调 AI, 放宽超时
    return request('/analyze', {
      method: 'POST',
      body: JSON.stringify({ match_id: matchId, provider, model, openid: getOpenid() }),
      timeout: 240000,
    })
  },
  getProviders() {
    return request('/providers')
  },
  async getQuota() {
    await ensureLogin()
    return request(`/quota?openid=${getOpenid()}`)
  },
  getSharedAnalysis(shareId) {
    return request(`/share/${shareId}`)
  },
  getCachedSmurf(playerId) {
    return request(`/smurf-check/${playerId}/cache`)
  },
  async smurfCheck(playerId) {
    await ensureLogin()
    return request(`/smurf-check/${playerId}?openid=${getOpenid()}`, { timeout: 60000 })
  },
  async bindSteam(steamInput) {
    await ensureLogin()
    return request('/user/bind', {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid(), steam_input: steamInput }),
      timeout: 30000,
    })
  },
  async getMyProfile() {
    await ensureLogin()
    return request(`/user/profile?openid=${getOpenid()}`, { timeout: 30000 })
  },
  async unbindSteam() {
    await ensureLogin()
    return request('/user/unbind', {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid() }),
    })
  },
  async getHistoryRank() {
    await ensureLogin()
    return request(`/user/history_rank?openid=${getOpenid()}`, { timeout: 60000 })
  },

  // ── 约战 ──
  async createChallenge(payload) {
    await ensureLogin()
    return request('/challenge/create', {
      method: 'POST',
      body: JSON.stringify({ ...payload, openid: getOpenid() }),
    })
  },
  async listChallenges() {
    await ensureLogin()
    return request(`/challenge/list?openid=${getOpenid()}`)
  },
  async myChallenges() {
    await ensureLogin()
    return request(`/challenge/mine?openid=${getOpenid()}`)
  },
  async getChallengeDetail(id) {
    // 分享空降用户首次打开也要先登录, 否则 openid=undefined 导致 joined/my_openid 判断错误
    await ensureLogin()
    return request(`/challenge/${id}?openid=${getOpenid()}`)
  },
  async joinChallenge(id, team) {
    await ensureLogin()
    return request(`/challenge/${id}/join`, {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid(), team }),
    })
  },
  async leaveChallenge(id) {
    await ensureLogin()
    return request(`/challenge/${id}/leave`, {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid() }),
    })
  },
  async switchTeam(id, team) {
    await ensureLogin()
    return request(`/challenge/${id}/switch_team`, {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid(), team }),
    })
  },
  async shuffleTeams(id) {
    await ensureLogin()
    return request(`/challenge/${id}/shuffle`, {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid() }),
    })
  },
  async swapParticipants(id, a, b) {
    await ensureLogin()
    return request(`/challenge/${id}/swap`, {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid(), participant_a: a, participant_b: b }),
    })
  },
  async updateChallenge(id, payload) {
    await ensureLogin()
    return request(`/challenge/${id}/update`, {
      method: 'POST',
      body: JSON.stringify({ ...payload, openid: getOpenid() }),
    })
  },
  async cancelChallenge(id) {
    await ensureLogin()
    return request(`/challenge/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid() }),
    })
  },
  async addChallengeMatch(id, matchId) {
    await ensureLogin()
    return request(`/challenge/${id}/match`, {
      method: 'POST',
      body: JSON.stringify({ openid: getOpenid(), match_id: matchId }),
      timeout: 60000,
    })
  },
  async listChallengeMatches(id) {
    return request(`/challenge/${id}/matches`, { timeout: 60000 })
  },
  async removeChallengeMatch(id, matchId) {
    await ensureLogin()
    return request(`/challenge/${id}/match/${matchId}?openid=${getOpenid()}`, {
      method: 'DELETE',
    })
  },
}

export function extractErr(e) {
  let msg = (e && e.message) || '请求失败'
  try { msg = JSON.parse(msg).detail || msg } catch (err) {}
  return msg
}

export function getCachedAnalysisLocal(matchId) {
  try {
    const raw = uni.getStorageSync(`${ANALYSIS_CACHE_PREFIX}${matchId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // timeline_source=game_log 表示真实比赛日志时间线;
    // 旧缓存 (AI 编造时间) 一律失效重新分析
    if (!parsed || !parsed.share_id || parsed.timeline_source !== 'game_log') return null
    return parsed
  } catch (e) {
    return null
  }
}

export function setCachedAnalysisLocal(matchId, result) {
  try {
    uni.setStorageSync(`${ANALYSIS_CACHE_PREFIX}${matchId}`, JSON.stringify(result))
  } catch (e) {}
}
