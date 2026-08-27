<script setup>
import { onMounted, nextTick, getCurrentInstance, watch } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] }, // [{t: ISO时间, v: rank_tier, rank_name}]
  width: { type: Number, default: 320 },
  height: { type: Number, default: 240 },
})

const cvId = 'step_' + Math.random().toString(36).slice(2, 10)
const inst = getCurrentInstance()

// 段位档位 1-8: 先锋 / 卫士 / 中军 / 统帅 / 传奇 / 万古 / 超凡 / 不朽
const RANK_LABELS = ['先锋', '卫士', '中军', '统帅', '传奇', '万古', '超凡', '不朽']
const ACCENT = '#d4a843'
const GRID = 'rgba(160,155,143,0.18)'
const INK_3 = '#a09b8f'
const INK_1 = '#3a352c'

onMounted(() => {
  // #ifdef H5
  drawH5()
  // #endif
  // #ifndef H5
  nextTick(() => drawMiniapp())
  // #endif
})

watch(() => props.data, () => {
  // #ifdef H5
  drawH5()
  // #endif
  // #ifndef H5
  nextTick(() => drawMiniapp())
  // #endif
}, { deep: true })

function drawH5() {
  nextTick(() => {
    const el = document.getElementById(cvId)
    if (!el) return
    const ctx = el.getContext('2d')
    draw(ctx, props.width, props.height)
  })
}

function drawMiniapp() {
  const query = inst && inst.proxy
    ? uni.createSelectorQuery().in(inst.proxy)
    : uni.createSelectorQuery()
  query
    .select('#' + cvId)
    .fields({ node: true, size: true })
    .exec((res) => {
      if (!res || !res[0] || !res[0].node) {
        drawLegacy()
        return
      }
      const canvas = res[0].node
      const ctx = canvas.getContext('2d')
      const dpr = (uni.getSystemInfoSync && uni.getSystemInfoSync().pixelRatio) || 1
      canvas.width = res[0].width * dpr
      canvas.height = res[0].height * dpr
      ctx.scale(dpr, dpr)
      draw(ctx, res[0].width, res[0].height)
    })
}

function drawLegacy() {
  const ctx = uni.createCanvasContext(cvId)
  draw(ctx, props.width, props.height)
  ctx.draw()
}

function draw(ctx, w, h) {
  ctx.clearRect && ctx.clearRect(0, 0, w, h)
  const data = (props.data || [])
    .map((d) => ({ ...d, ts: Date.parse(d.t), v: Number(d.v) }))
    .filter((d) => Number.isFinite(d.ts) && Number.isFinite(d.v))
    .sort((a, b) => a.ts - b.ts)

  if (!data.length) {
    ctx.fillStyle = INK_3
    ctx.font = '13px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('暂无历史段位数据', w / 2, h / 2)
    return
  }

  const padL = 56, padR = 20, padT = 24, padB = 30
  const innerW = w - padL - padR
  const innerH = h - padT - padB

  // Y 轴: 数据段位范围 ±1 档, 至少跨 3 档, 钳制在 1-8
  let minT = Math.floor(Math.min(...data.map((d) => d.v)) / 10) || 1
  let maxT = Math.floor(Math.max(...data.map((d) => d.v)) / 10) || 8
  minT = Math.max(1, minT - 1)
  maxT = Math.min(8, maxT + 1)
  if (maxT - minT < 2) {
    minT = Math.max(1, minT - 1)
    maxT = Math.min(8, maxT + 1)
  }
  const tSpan = maxT - minT || 1

  // X 轴: 时间线性映射
  const minTs = data[0].ts
  const maxTs = data[data.length - 1].ts
  const tsSpan = Math.max(maxTs - minTs, 1)

  const xOf = (ts) => padL + ((ts - minTs) / tsSpan) * innerW
  const yOf = (v) => {
    const f = (v / 10 - minT) / tSpan
    return padT + innerH - Math.max(0, Math.min(1, f)) * innerH
  }

  // 横向网格线 + Y 轴档位标签
  ctx.font = '11px sans-serif'
  ctx.textBaseline = 'middle'
  for (let t = minT; t <= maxT; t++) {
    const y = padT + innerH - ((t - minT) / tSpan) * innerH
    ctx.strokeStyle = GRID
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(padL, y)
    ctx.lineTo(w - padR, y)
    ctx.stroke()
    ctx.fillStyle = INK_3
    ctx.textAlign = 'right'
    ctx.fillText(RANK_LABELS[t - 1] || `T${t}`, padL - 8, y)
  }

  // X 轴标签: 跨年显示年份, 一年内显示月份
  const firstD = new Date(minTs)
  const lastD = new Date(maxTs)
  const monthSpan = (lastD.getFullYear() - firstD.getFullYear()) * 12 + (lastD.getMonth() - firstD.getMonth())
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  ctx.fillStyle = INK_3
  if (monthSpan > 14) {
    // 按年份: 取每年 1 月或首个数据点所在位置
    const years = []
    for (let y = firstD.getFullYear(); y <= lastD.getFullYear(); y++) years.push(y)
    const step = years.length > 6 ? Math.ceil(years.length / 6) : 1
    years.forEach((y, i) => {
      if (i % step !== 0 && i !== years.length - 1) return
      const ts = Math.max(minTs, Date.parse(`${y}-01-01`))
      ctx.fillText(String(y), xOf(Math.min(ts, maxTs)), h - padB + 8)
    })
  } else {
    // 按月: 每 1-2 月一个刻度
    const step = monthSpan > 6 ? 2 : 1
    let y = firstD.getFullYear(), m = firstD.getMonth()
    const labels = []
    while (Date.parse(`${y}-${String(m + 1).padStart(2, '0')}-01`) <= maxTs) {
      labels.push({ ts: Math.max(minTs, Date.parse(`${y}-${String(m + 1).padStart(2, '0')}-01`)), label: `${m + 1}月` })
      m += step
      while (m >= 12) { m -= 12; y += 1 }
    }
    labels.forEach((l, i) => {
      if (i > 0 && i === labels.length - 1 && labels.length > 6) return
      ctx.fillText(l.label, xOf(Math.min(l.ts, maxTs)), h - padB + 8)
    })
  }

  // 面积填充
  ctx.beginPath()
  data.forEach((d, i) => {
    const x = xOf(d.ts), y = yOf(d.v)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.lineTo(xOf(maxTs), padT + innerH)
  ctx.lineTo(xOf(minTs), padT + innerH)
  ctx.closePath()
  ctx.fillStyle = 'rgba(212,168,67,0.15)'
  ctx.fill()

  // 折线
  ctx.beginPath()
  ctx.strokeStyle = ACCENT
  ctx.lineWidth = 2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  data.forEach((d, i) => {
    const x = xOf(d.ts), y = yOf(d.v)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.stroke()

  // 数据点
  ctx.fillStyle = ACCENT
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = 1.5
  const dotR = data.length > 20 ? 2 : 3
  for (const d of data) {
    ctx.beginPath()
    ctx.arc(xOf(d.ts), yOf(d.v), dotR, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  }

  // 首尾段位标注
  ctx.fillStyle = INK_1
  ctx.font = '11px sans-serif'
  ctx.textBaseline = 'bottom'
  const first = data[0]
  const last = data[data.length - 1]
  ctx.textAlign = 'left'
  ctx.fillText(first.rank_name || RANK_LABELS[Math.floor(first.v / 10) - 1] || '', xOf(first.ts) + 6, yOf(first.v) - 5)
  ctx.textAlign = 'right'
  ctx.fillText(last.rank_name || RANK_LABELS[Math.floor(last.v / 10) - 1] || '', xOf(last.ts) - 6, yOf(last.v) - 5)
}
</script>

<template>
  <view class="step-wrap">
    <!-- #ifdef H5 -->
    <canvas :id="cvId" :width="width" :height="height" class="step-cv" />
    <!-- #endif -->
    <!-- #ifndef H5 -->
    <canvas
      :id="cvId"
      :canvas-id="cvId"
      type="2d"
      class="step-cv"
      :style="{ width: width + 'px', height: height + 'px' }"
    />
    <!-- #endif -->
  </view>
</template>

<style scoped>
.step-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
}
.step-cv {
  background: transparent;
}
</style>
