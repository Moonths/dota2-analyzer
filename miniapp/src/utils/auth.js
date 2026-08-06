let _openid = ''

export function getOpenid() { return _openid }

export async function login() {
  try {
    const { code } = await uni.login({ provider: 'weixin' })
    // #ifdef H5
    const loginUrl = '/dota-api/login'
    // #endif
    // #ifndef H5
    const loginUrl = 'https://maojike.me/dota-api/login'
    // #endif
    const res = await uni.request({
      url: loginUrl,
      method: 'POST',
      data: { code },
      header: { 'Content-Type': 'application/json' },
    })
    if (res.statusCode === 200 && res.data.openid) {
      _openid = res.data.openid
    }
  } catch (e) {
    // 登录失败降级：用设备标识
    const sys = uni.getSystemInfoSync()
    _openid = 'device_' + (sys.deviceId || sys.model + '_' + Date.now())
  }
}
