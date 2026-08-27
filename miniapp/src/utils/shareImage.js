/**
 * 绘制分享卡片 — Canvas 2D API
 *
 * 之前导出一直失败的三个原因（已修）:
 * 1. Canvas 2D 绘制命令是异步提交的，画完立即导出会拿到空图 → 现在等一帧(canvas.requestAnimationFrame)
 * 2. canvasToTempFilePath 失败被静默吞掉 → 现在 console.error 输出 errMsg
 * 3. canvas 移出视口(left:-9999px)部分真机不渲染 → 配合页面里改为视口内 opacity:0
 */

function getDpr() {
  try {
    const win = uni.getWindowInfo ? uni.getWindowInfo() : null
    if (win && win.pixelRatio) return win.pixelRatio
  } catch (e) {}
  try {
    return uni.getSystemInfoSync().pixelRatio || 2
  } catch (e) {
    return 2
  }
}

function getCanvas() {
  return new Promise((resolve) => {
    const query = uni.createSelectorQuery()
    query.select('#shareCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) {
          console.error('[shareImage] 找不到 #shareCanvas 节点')
          resolve(null)
          return
        }
        const canvas = res[0].node
        const dpr = getDpr()
        canvas.width = 250 * dpr
        canvas.height = 200 * dpr
        const ctx = canvas.getContext('2d')
        ctx.scale(dpr, dpr)
        resolve(canvas)
      })
  })
}

/** 等一帧，让 Canvas 2D 的异步绘制命令真正提交后再导出 */
function nextFrame(canvas, fn) {
  if (canvas && typeof canvas.requestAnimationFrame === 'function') {
    canvas.requestAnimationFrame(() => fn())
  } else {
    setTimeout(fn, 120)
  }
}

function canvasToFile(canvas) {
  return new Promise((resolve) => {
    const doExport = () => {
      const opts = {
        canvas,
        // 导出尺寸与实际像素一致，避免模糊
        destWidth: canvas.width,
        destHeight: canvas.height,
        fileType: 'png',
        success(res) { resolve(res.tempFilePath) },
        fail(err) {
          console.error('[shareImage] canvasToTempFilePath 失败:', err && err.errMsg)
          resolve('')
        },
      }
      // #ifdef MP-WEIXIN
      wx.canvasToTempFilePath({ ...opts })
      // #endif
      // #ifndef MP-WEIXIN
      uni.canvasToTempFilePath({ ...opts })
      // #endif
    }
    nextFrame(canvas, doExport)
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
