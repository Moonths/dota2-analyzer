/**
 * 绘制分享卡片 — Canvas 2D API
 */

function getCanvas() {
  return new Promise((resolve) => {
    const query = uni.createSelectorQuery()
    query.select('#shareCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) {
          resolve(null)
          return
        }
        const canvas = res[0].node
        const dpr = uni.getSystemInfoSync().pixelRatio
        canvas.width = 250 * dpr
        canvas.height = 200 * dpr
        const ctx = canvas.getContext('2d')
        ctx.scale(dpr, dpr)
        resolve(canvas)
      })
  })
}

function canvasToFile(canvas) {
  return new Promise((resolve) => {
    uni.canvasToTempFilePath({
      canvas,
      quality: 0.9,
      success(res) { resolve(res.tempFilePath) },
      fail() { resolve('') },
    })
  })
}

function wrapText(ctx, text, maxWidth) {
  const lines = []
  let cur = ''
  for (const ch of text) {
    const test = cur + ch
    const metrics = ctx.measureText(test)
    if (metrics.width > maxWidth) {
      lines.push(cur)
      cur = ch
    } else {
      cur = test
    }
  }
  if (cur) lines.push(cur)
  return lines
}

/**
 * 绘制背锅侠分享卡片
 */
export function drawShareCard(sg, mvp) {
  return new Promise(async (resolve) => {
    // #ifdef MP-WEIXIN
    const canvas = await getCanvas()
    if (!canvas) { resolve(''); return }
    const ctx = canvas.getContext('2d')
    const W = 250, H = 200

    // 背景
    ctx.fillStyle = '#111110'
    ctx.fillRect(0, 0, W, H)

    // 红色顶栏
    ctx.fillStyle = '#d93d36'
    ctx.fillRect(0, 0, W, 36)
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 14px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('🤡 分锅大会 · 背锅侠揭晓', W / 2, 26)

    // 玩家名
    ctx.fillStyle = '#ede8dc'
    ctx.font = 'bold 13px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText(sg.player_name || '', 16, 56)

    // 英雄 + 位置
    ctx.fillStyle = '#a09b8f'
    ctx.font = '9px sans-serif'
    ctx.fillText('英雄: ' + (sg.hero_name || '') + '  |  ' + (sg.position ? sg.position + '号位' : ''), 16, 72)

    // 数据
    ctx.fillStyle = '#6b675e'
    ctx.font = '8px sans-serif'
    ctx.fillText('KDA ' + (sg.kda || '') + '  |  GPM ' + (sg.gpm || 0) + '  |  XPM ' + (sg.xpm || 0), 16, 86)

    // 分割线
    ctx.strokeStyle = 'rgba(156,147,132,.18)'
    ctx.lineWidth = 0.5
    ctx.beginPath()
    ctx.moveTo(16, 98)
    ctx.lineTo(W - 16, 98)
    ctx.stroke()

    // 背锅理由
    ctx.fillStyle = '#a09b8f'
    ctx.font = '8px sans-serif'
    const reason = sg.reason || ''
    const lines = wrapText(ctx, reason, W - 32)
    lines.forEach((l, i) => {
      if (i < 4) ctx.fillText(l, 16, 112 + i * 13)
    })

    // MVP 脚注
    ctx.fillStyle = '#6b675e'
    ctx.font = '7px sans-serif'
    ctx.textAlign = 'right'
    ctx.fillText('🏆 MVP: ' + (mvp.player_name || '') + ' (' + (mvp.hero_name || '') + ')', W - 16, H - 16)
    ctx.textAlign = 'center'
    ctx.font = '6px sans-serif'
    ctx.fillText('扫码进入分锅大会，看看谁在犯罪', W / 2, H - 4)

    const path = await canvasToFile(canvas)
    resolve(path)
    // #endif
    // #ifndef MP-WEIXIN
    resolve('')
    // #endif
  })
}

/**
 * 绘制首页 slogan 分享卡片
 */
export function drawHomeCard() {
  return new Promise(async (resolve) => {
    // #ifdef MP-WEIXIN
    const canvas = await getCanvas()
    if (!canvas) { resolve(''); return }
    const ctx = canvas.getContext('2d')
    const W = 250, H = 200

    ctx.fillStyle = '#111110'
    ctx.fillRect(0, 0, W, H)

    // 金边
    ctx.fillStyle = '#d4a843'
    ctx.fillRect(0, 0, W, 2)
    ctx.fillRect(0, H - 2, W, 2)

    const slogans = ['谁尽力 谁犯罪', '谁的打法不团队', '谁在see 谁针对', '是谁野区把线对', '谁勇敢 谁暴毙', '又是谁没人情味？']
    ctx.fillStyle = '#ede8dc'
    ctx.font = 'bold 12px sans-serif'
    ctx.textAlign = 'center'
    slogans.forEach((l, i) => ctx.fillText(l, W / 2, 48 + i * 22))

    ctx.fillStyle = '#d4a843'
    ctx.font = 'bold 10px sans-serif'
    ctx.fillText('—— 分锅大会 ——', W / 2, H - 12)

    const path = await canvasToFile(canvas)
    resolve(path)
    // #endif
    // #ifndef MP-WEIXIN
    resolve('')
    // #endif
  })
}
