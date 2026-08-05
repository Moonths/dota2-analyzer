/**
 * 绘制背锅侠分享卡片
 * @param {Object} sg - scapegoat card {player_name, hero_name, hero_icon, kda, gpm, xpm, reason}
 * @param {Object} mvp - mvp card {player_name, hero_name}
 * @returns {Promise<string>} temp file path
 */
export function drawShareCard(sg, mvp) {
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    const ctx = uni.createCanvasContext('shareCanvas')
    const W = 250, H = 200

    // 背景
    ctx.setFillStyle('#111110')
    ctx.fillRect(0, 0, W, H)

    // 红色顶栏
    ctx.setFillStyle('#d93d36')
    ctx.fillRect(0, 0, W, 36)
    ctx.setFillStyle('#ffffff')
    ctx.setFontSize(14)
    ctx.setTextAlign('center')
    ctx.fillText('🤡 分锅大会 · 背锅侠揭晓', W / 2, 24)

    // 英雄图标 - drawImage needs local path, skip for network images
    // Player name
    ctx.setFillStyle('#ede8dc')
    ctx.setFontSize(13)
    ctx.setTextAlign('left')
    ctx.fillText(sg.player_name || '', 16, 55)

    // Hero + position
    ctx.setFillStyle('#a09b8f')
    ctx.setFontSize(9)
    ctx.fillText('英雄: ' + (sg.hero_name || '') + '  |  ' + (sg.position ? sg.position + '号位' : ''), 16, 72)

    // Stats
    ctx.setFillStyle('#6b675e')
    ctx.setFontSize(8)
    ctx.fillText('KDA ' + (sg.kda || '') + '  |  GPM ' + (sg.gpm || 0) + '  |  XPM ' + (sg.xpm || 0), 16, 86)

    // Divider
    ctx.setStrokeStyle('rgba(156,147,132,.18)')
    ctx.setLineWidth(0.5)
    ctx.beginPath()
    ctx.moveTo(16, 98)
    ctx.lineTo(W - 16, 98)
    ctx.stroke()

    // Reason text (wrapped)
    ctx.setFillStyle('#a09b8f')
    ctx.setFontSize(8)
    const reason = sg.reason || ''
    const lines = wrapText(reason, 37)
    lines.forEach((l, i) => {
      if (i < 3) ctx.fillText(l, 16, 112 + i * 13)
    })

    // MVP footer
    ctx.setFillStyle('#6b675e')
    ctx.setFontSize(7)
    ctx.setTextAlign('right')
    ctx.fillText('🏆 MVP: ' + (mvp.player_name || '') + ' (' + (mvp.hero_name || '') + ')', W - 16, H - 16)
    ctx.setTextAlign('center')
    ctx.setFontSize(6)
    ctx.fillText('扫码进入分锅大会，看看谁在犯罪', W / 2, H - 5)

    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath({
          canvasId: 'shareCanvas',
          quality: 0.9,
          success(res) { resolve(res.tempFilePath) },
          fail() { resolve('') },
        })
      }, 300)
    })
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
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    const ctx = uni.createCanvasContext('shareCanvas')
    const W = 250, H = 200

    ctx.setFillStyle('#111110')
    ctx.fillRect(0, 0, W, H)

    // Gold borders
    ctx.setFillStyle('#d4a843')
    ctx.fillRect(0, 0, W, 2)
    ctx.fillRect(0, H - 2, W, 2)

    const slogans = ['谁尽力 谁犯罪', '谁的打法不团队', '谁在see 谁针对', '是谁野区把线对', '谁勇敢 谁暴毙', '又是谁没人情味？']
    ctx.setFillStyle('#ede8dc')
    ctx.setFontSize(12)
    ctx.setTextAlign('center')
    slogans.forEach((l, i) => ctx.fillText(l, W / 2, 45 + i * 22))

    ctx.setFillStyle('#d4a843')
    ctx.setFontSize(10)
    ctx.fillText('—— 分锅大会 ——', W / 2, H - 12)

    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath({
          canvasId: 'shareCanvas',
          quality: 0.9,
          success(res) { resolve(res.tempFilePath) },
          fail() { resolve('') },
        })
      }, 300)
    })
    // #endif
    // #ifndef MP-WEIXIN
    resolve('')
    // #endif
  })
}

function wrapText(text, maxCharsPerLine) {
  const lines = []
  let cur = ''
  for (const ch of text) {
    if (cur.length >= maxCharsPerLine) { lines.push(cur); cur = ch }
    else { cur += ch }
  }
  if (cur) lines.push(cur)
  return lines
}
