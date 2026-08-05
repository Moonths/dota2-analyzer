// 广告单元ID，需在微信公众平台 → 流量主 → 广告管理 中获取
// 开发阶段可用测试ID，正式发布前替换
const AD_UNIT_IDS = {
  interstitial: 'adunit-616a14c1fa732a1d',  // 插屏广告测试ID，发布前替换
  banner: 'adunit-7a6e38e0f5c2c1d3',        // Banner广告测试ID，发布前替换
}

/**
 * 展示插屏广告，返回 Promise
 * 用户关闭广告后 resolve，广告加载失败直接 resolve（不阻断流程）
 */
export function showInterstitialAd() {
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    const interstitialAd = wx.createInterstitialAd({
      adUnitId: AD_UNIT_IDS.interstitial,
    })

    interstitialAd.onLoad(() => {
      interstitialAd.show().catch(() => {
        resolve()
      })
    })

    interstitialAd.onError(() => {
      resolve()
    })

    interstitialAd.onClose(() => {
      resolve()
    })
    // #endif

    // #ifndef MP-WEIXIN
    resolve()
    // #endif
  })
}

/**
 * 创建 Banner 广告实例，用于页面中展示
 * 返回广告实例或 null
 */
export function createBannerAd(containerId) {
  // #ifdef MP-WEIXIN
  try {
    const bannerAd = wx.createBannerAd({
      adUnitId: AD_UNIT_IDS.banner,
      adIntervals: 30,
      style: {
        left: 0,
        top: 0,
        width: 375,
      },
    })
    bannerAd.onError(() => {})
    return bannerAd
  } catch (e) {
    return null
  }
  // #endif

  // #ifndef MP-WEIXIN
  return null
  // #endif
}

export default { showInterstitialAd, createBannerAd, AD_UNIT_IDS }
