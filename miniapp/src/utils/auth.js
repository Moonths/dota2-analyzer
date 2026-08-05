let _openid = ''

export function getOpenid() { return _openid }

export async function login() {
  try {
    const { code } = await uni.login({ provider: 'weixin' })
    const res = await uni.request({
      url: 'https://maojike.me/dota-api/login',
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
