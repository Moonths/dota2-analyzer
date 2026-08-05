const BASE = 'https://maojike.me/dota-api'

function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE + url,
      method: options.method || 'GET',
      data: options.body ? JSON.parse(options.body) : undefined,
      header: { 'Content-Type': 'application/json' },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const err = typeof res.data === 'string' ? res.data : JSON.stringify(res.data)
          reject(new Error(err || `HTTP ${res.statusCode}`))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || 'Network error'))
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
  analyze(matchId, provider, model) {
    return request('/analyze', {
      method: 'POST',
      body: JSON.stringify({ match_id: matchId, provider, model }),
    })
  },
  getProviders() {
    return request('/providers')
  },
  getSharedAnalysis(shareId) {
    return request(`/share/${shareId}`)
  },
}
