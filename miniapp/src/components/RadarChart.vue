<script setup>
import { ref, onMounted, nextTick, getCurrentInstance } from 'vue'

const props = defineProps({
  scores: { type: Object, required: true }, // {kda, eco, exp, dmg, push, sustain} 0-100
  size: { type: Number, default: 180 },
})

// 唯一 canvas id, 避免同页多组件冲突
const cvId = 'radar_' + Math.random().toString(36).slice(2, 10)

// setup 顶层同步拿 instance (onMounted 回调里 getCurrentInstance 会返回 null)
const inst = getCurrentInstance()

// 小程序端: 画完导出成图片显示 (canvas 同层渲染在长列表滚动时会颤动, image 不会)
const imgSrc = ref('')

const AXES = [
  { key: 'kda', label: 'KDA' },
  { key: 'eco', label: '经济' },
  { key: 'exp', label: '经验' },
  { key: 'dmg', label: '输出' },
  { key: 'push', label: '推塔' },
  { key: 'sustain', label: '治疗' },
]

onMounted(() => {
  // #ifdef H5
  drawH5()
  // #endif
  // #ifndef H5
  nextTick(() => drawMiniapp())
  // #endif
})

// H5: 直接拿 DOM canvas
function drawH5() {
  nextTick(() => {
    const el = document.getElementById(cvId)
    if (!el) return
    const ctx = el.getContext('2d')
    draw(ctx, props.size, props.size)
  })
}

// 小程序: 用 SelectorQuery 拿 canvas node (新 2d API)
function drawMiniapp() {
  const query = inst && inst.proxy
    ? uni.createSelectorQuery().in(inst.proxy)
    : uni.createSelectorQuery()
  query
    .select('#' + cvId)
    .fields({ node: true, size: true })
    .exec((res) => {
      if (!res || !res[0] || !res[0].node) {
        // 降级: 老接口 createCanvasContext (兼容旧基础库)
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
      exportImage(canvas)
    })
}

// 画完转图片: 根治长列表滚动时 canvas 原生层颤动
function exportImage(canvas) {
  // #ifdef MP-WEIXIN
  const _toTemp = () => {
    wx.canvasToTempFilePath({
      canvas,
      success: (r) => { if (r.tempFilePath) imgSrc.value = r.tempFilePath },
      fail: () => {},
    })
  }
  // 等一帧再导出, 保证绘制指令已消费 (真机坑)
  if (canvas.requestAnimationFrame) {
    canvas.requestAnimationFrame(() => canvas.requestAnimationFrame(_toTemp))
  } else {
    setTimeout(_toTemp, 50)
  }
  // #endif
}

// 降级: 用老 canvas API (createCanvasContext), 不依赖 type="2d"
function drawLegacy() {
  const ctx = uni.createCanvasContext(cvId)
  draw(ctx, props.size, props.size)
  ctx.draw()
}

function draw(ctx, w, h) {
  const cx = w / 2
  const cy = h / 2
  const r = Math.min(w, h) / 2 - 20 // 留边给标签
  const angles = AXES.map((_, i) => -Math.PI / 2 + (i * Math.PI) / 3)
  const pt = (frac, i) => {
    const rr = r * frac
    return [cx + rr * Math.cos(angles[i]), cy + rr * Math.sin(angles[i])]
  }

  // 背景网格 4 层
  ctx.strokeStyle = 'rgba(160,155,143,0.18)'
  ctx.lineWidth = 1
  for (let g = 1; g <= 4; g++) {
    ctx.beginPath()
    for (let i = 0; i < 6; i++) {
      const [x, y] = pt(g / 4, i)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.closePath()
    ctx.stroke()
  }

  // 轴线
  ctx.strokeStyle = 'rgba(160,155,143,0.12)'
  for (let i = 0; i < 6; i++) {
    const [x, y] = pt(1, i)
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(x, y)
    ctx.stroke()
  }

  // 数据多边形
  ctx.beginPath()
  ctx.fillStyle = 'rgba(212,168,67,0.25)'
  ctx.strokeStyle = '#d4a843'
  ctx.lineWidth = 2
  for (let i = 0; i < 6; i++) {
    const v = (Number(props.scores[AXES[i].key]) || 0) / 100
    const [x, y] = pt(Math.max(0, Math.min(1, v)), i)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // 数据点
  ctx.fillStyle = '#d4a843'
  for (let i = 0; i < 6; i++) {
    const v = (Number(props.scores[AXES[i].key]) || 0) / 100
    const [x, y] = pt(Math.max(0, Math.min(1, v)), i)
    ctx.beginPath()
    ctx.arc(x, y, 2.5, 0, Math.PI * 2)
    ctx.fill()
  }

  // 标签
  ctx.fillStyle = '#a09b8f'
  ctx.font = '11px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  for (let i = 0; i < 6; i++) {
    const [x, y] = pt(1.18, i)
    ctx.fillText(AXES[i].label, x, y)
  }
}
</script>

<template>
  <view class="radar-wrap">
    <!-- #ifdef H5 -->
    <canvas :id="cvId" :width="size" :height="size" class="radar-cv" />
    <!-- #endif -->
    <!-- #ifndef H5 -->
    <!-- 转图片后用 image 显示, 根治滚动颤动; 导出前先显示 canvas -->
    <image
      v-if="imgSrc"
      :src="imgSrc"
      class="radar-img"
      :style="{ width: size + 'px', height: size + 'px' }"
    />
    <canvas
      v-show="!imgSrc"
      :id="cvId"
      :canvas-id="cvId"
      type="2d"
      class="radar-cv"
      :style="{ width: size + 'px', height: size + 'px' }"
    />
    <!-- #endif -->
  </view>
</template>

<style scoped>
.radar-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
}
.radar-cv {
  background: transparent;
}
.radar-img {
  display: block;
}
</style>
