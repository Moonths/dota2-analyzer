const OPENID_KEY = 'dota2_openid'

// 登录地址跟随 API 基地址，避免开发/生产环境切换时域名不一致。
const API_BASE = (function () {
  // #ifdef H5
  return '/dota-api'
  // #endif
  // #ifndef H5
  return __API_BASE__
  // #endif
})()

let _openid = ''
let _loginPromise = null

export function getOpenid() {
  return _openid
}

function persistOpenid(openid) {
  _openid = openid
  try {
    uni.setStorageSync(OPENID_KEY, openid)
  } catch (e) {
    // 存储失败不影响本次请求，使用内存中的 openid。
  }
}

function loadFallbackOpenid() {
  try {
    return uni.getStorageSync(OPENID_KEY) || ''
  } catch (e) {
    return ''
  }
}

export async function login() {
  try {
    const { code } = await uni.login({ provider: 'weixin' })
    const res = await uni.request({
      url: API_BASE + '/login',
      method: 'POST',
      data: { code },
      header: { 'Content-Type': 'application/json' },
    })
    if (res.statusCode === 200 && res.data && res.data.openid) {
      persistOpenid(res.data.openid)
      return res.data.openid
    }
  } catch (e) {
    // 登录失败时降级，但保持同一个设备 ID，避免每日额度被反复重置。
  }

  const cached = loadFallbackOpenid()
  if (cached) {
    _openid = cached
    return cached
  }

  const sys = uni.getSystemInfoSync()
  const stableId = sys.deviceId || sys.model || 'weixin'
  const fallback = `device_${stableId}_${Date.now()}`
  persistOpenid(fallback)
  return fallback
}

export function ensureLogin() {
  if (_openid) return Promise.resolve(_openid)
  if (!_loginPromise) {
    _loginPromise = login().finally(() => {
      _loginPromise = null
    })
  }
  return _loginPromise
}
