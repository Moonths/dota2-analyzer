<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { onShareAppMessage } from '@dcloudio/uni-app'
import { api } from '../../api/index.js'
import { heroImg } from '../../utils/image.js'
import { drawHomeCard } from '../../utils/shareImage.js'

const HISTORY_KEY = 'dota2_search_history'

const searchMode = ref('player')
const playerId = ref('')
const matchId = ref('')
const loading = ref(false)
const error = ref('')
const playerName = ref('')
const matches = ref([])
const selectedProvider = ref('deepseek')
const selectedModel = ref('deepseek-chat')
const searchHistory = ref([])
const shareImagePath = ref()
const showHistory = ref(false)

// ── 捕鱼执法 ──
const smurfId = ref('')
const smurfLoading = ref(false)
const smurfConfirming = ref(false)
const smurfError = ref('')
const smurfResult = ref(null)
const smurfExpanded = ref(false)
const smurfCacheHint = ref('')
const smurfLoadingText = ref('正在调取玩家战绩...')
const smurfLoadingTexts = [
  '正在调取玩家战绩...',
  '正在逐场核对比赛数据...',
  '正在比对英雄基准...',
  '正在给这条鱼定罪...',
]
let smurfTextTimer = null
let smurfTextIndex = 0
let smurfRequestSeq = 0
let smurfLastRunAt = 0

function beginSmurfLoading() {
  smurfTextIndex = 0
  smurfLoadingText.value = smurfLoadingTexts[0]
  smurfTextTimer = setInterval(() => {
    smurfTextIndex = (smurfTextIndex + 1) % smurfLoadingTexts.length
    smurfLoadingText.value = smurfLoadingTexts[smurfTextIndex]
  }, 1600)
}

function endSmurfLoading() {
  if (smurfTextTimer) {
    clearInterval(smurfTextTimer)
    smurfTextTimer = null
  }
}

onUnmounted(endSmurfLoading)

onMounted(() => {
  drawHomeCard().then(p => { shareImagePath.value = p })
  const saved = uni.getStorageSync('dota2_player_id')
  if (saved) playerId.value = saved
  loadHistory()
  loadProviders()
})

function loadHistory() {
  try { searchHistory.value = uni.getStorageSync(HISTORY_KEY) || [] } catch (e) { searchHistory.value = [] }
}

function saveHistory(type, value, label) {
  const item = { type, value, label }
  let list = searchHistory.value.filter(h => h.value !== value)
  list.unshift(item)
  if (list.length > 3) list = list.slice(0, 3)
  searchHistory.value = list
  uni.setStorageSync(HISTORY_KEY, list)
}

function selectHistory(item) {
  if (item.type === 'player') { searchMode.value = 'player'; playerId.value = item.value }
  else if (item.type === 'match') { searchMode.value = 'match'; matchId.value = item.value }
  else if (item.type === 'smurf') { searchMode.value = 'smurf'; smurfId.value = item.value }
  showHistory.value = false
}

async function loadProviders() {
  try {
    const data = await api.getProviders()
    if (data.providers.length > 0) {
      const preferred = data.providers.find(p => p.id === 'deepseek') || data.providers[0]
      selectedProvider.value = preferred.id
      selectedModel.value = preferred.models[0]
    }
  } catch (e) {}
}

async function searchPlayer() {
  const id = parseInt(playerId.value.trim())
  if (!id) { error.value = '请输入有效的玩家ID'; return }
  loading.value = true; error.value = ''
  uni.setStorageSync('dota2_player_id', playerId.value.trim())
  const val = playerId.value.trim()
  try {
    const data = await api.getPlayerMatches(id)
    playerName.value = data.player_name
    matches.value = data.matches
    saveHistory('player', val, `玩家 ${val}`)
    showHistory.value = false
  } catch (e) {
    error.value = e.message || '搜索失败'
    matches.value = []
  } finally { loading.value = false }
}

function analyzeMatch(id) {
  const url = `/pages/analysis/analysis?matchId=${id}&provider=${selectedProvider.value}&model=${selectedModel.value}`
  uni.navigateTo({ url })
}

function goDirectMatch() {
  const val = matchId.value.trim()
  const id = parseInt(val)
  if (!id) { error.value = '请输入有效的比赛ID'; return }
  saveHistory('match', val, `比赛 ${val}`)
  showHistory.value = false
  analyzeMatch(id)
}

function confirmQuota(kind) {
  return api.getQuota().then((quota) => {
    const remaining = quota && typeof quota.remaining === 'number'
      ? quota.remaining
      : (quota && typeof quota.analysis_remaining === 'number' ? quota.analysis_remaining : 0)
    if (remaining <= 0) {
      uni.showToast({ title: '今天 3 次分析机会已用完，明天再来！', icon: 'none', duration: 2500 })
      return false
    }
    const label = kind === 'analysis' ? '比赛分析' : '小号检测'
    return new Promise((resolve) => {
      uni.showModal({
        title: '今日分析机会',
        content: `本次${label}会消耗 1 次机会，今天还剩 ${remaining} 次。`,
        confirmText: kind === 'analysis' ? '继续分析' : '继续检测',
        cancelText: '先不',
        success: (res) => resolve(!!res.confirm),
        fail: () => resolve(false),
      })
    })
  }).catch(() => true)
}

// Vue3 setup 中必须通过 uni-app 导入注册，直接声明 function 不会生效
onShareAppMessage(() => ({
  imageUrl: shareImagePath.value,
  title: '分锅大会 —— 谁尽力谁犯罪，AI判官为你揭晓',
  path: '/pages/index/index',
}))

// ── 捕鱼执法 ──
async function runSmurfCheck() {
  const now = Date.now()
  if (smurfLoading.value || smurfConfirming.value || now - smurfLastRunAt < 600) return
  const id = parseInt(smurfId.value.trim())
  if (!id) { smurfError.value = '请输入有效的玩家ID'; return }

  smurfLastRunAt = now
  smurfConfirming.value = true
  try {
    try {
      const cached = await api.getCachedSmurf(id)
      if (cached && typeof cached.score === 'number') {
        smurfResult.value = cached
        smurfExpanded.value = false
        smurfCacheHint.value = cached.message || '已使用小号检测缓存，不消耗今日次数'
        return
      }
    } catch (e) {}

    if (!(await confirmQuota('smurf'))) return
  } finally {
    smurfConfirming.value = false
  }

  const seq = ++smurfRequestSeq
  smurfLoading.value = true; smurfError.value = ''
  smurfResult.value = null; smurfExpanded.value = false; smurfCacheHint.value = ''
  beginSmurfLoading()
  try {
    const result = await api.smurfCheck(id)
    if (seq === smurfRequestSeq) {
      smurfResult.value = result
      smurfCacheHint.value = result.cached ? (result.message || '已使用缓存，不消耗次数') : ''
      saveHistory('smurf', id.toString(), `查小号 ${id}`)
      showHistory.value = false
    }
  } catch (e) {
    if (seq === smurfRequestSeq) smurfError.value = e.message || '检测失败'
  } finally {
    if (seq === smurfRequestSeq) {
      endSmurfLoading()
      smurfLoading.value = false
    }
  }
}

function smurfLabel(score) {
  if (score >= 0.85) return '极高'
  if (score >= 0.70) return '很高'
  if (score >= 0.55) return '较高'
  if (score >= 0.40) return '中等'
  return '较低'
}

function smurfColor(score) {
  if (score >= 0.70) return 'var(--down)'
  if (score >= 0.55) return 'var(--warn)'
  if (score >= 0.40) return 'var(--accent)'
  return 'var(--up)'
}

function onInputFocus() { showHistory.value = searchHistory.value.length > 0 }
function onInputBlur() { setTimeout(() => { showHistory.value = false }, 200) }

function formatDuration(sec) { const m = Math.floor(sec / 60); const s = sec % 60; return `${m}:${s.toString().padStart(2, '0')}` }
function formatTime(ts) { return new Date(ts * 1000).toLocaleDateString('zh-CN') }
</script>

<template>
  <view class="home">
    <image class="home-bg" src="/static/dota2-bg.jpg" mode="aspectFill" />
    <view class="home-mask"></view>
    <view class="hero">
      <view class="container">
        <text class="hero-title">谁尽力 谁犯罪</text>
        <text class="hero-title" style="font-size:56rpx;">谁的打法不团队</text>
        <text class="hero-sub">谁在see 谁针对 是谁野区把线对</text>
        <text class="hero-sub">谁勇敢 谁暴毙 又是谁没人情味？</text>

        <view class="mode-tabs">
          <view :class="['mode-tab',{active:searchMode==='player'}]" @click="searchMode='player'"><text>搜玩家</text></view>
          <view :class="['mode-tab',{active:searchMode==='match'}]" @click="searchMode='match'"><text>比赛ID</text></view>
          <view :class="['mode-tab',{active:searchMode==='smurf'}]" @click="searchMode='smurf'"><text>捕鱼执法</text></view>
        </view>

        <!-- 搜玩家 -->
        <view v-if="searchMode==='player'" class="search-bar">
          <view class="search-input-wrap">
            <input v-model="playerId" type="number" placeholder="输入玩家ID（Steam32 ID）" class="search-input" @confirm="searchPlayer" @focus="onInputFocus" @blur="onInputBlur" />
            <view class="history-dropdown" v-if="showHistory && searchHistory.length > 0">
              <view v-for="(h,i) in searchHistory" :key="i" class="history-item" @click="selectHistory(h)">
                <text class="history-label">{{ h.label }}</text>
                <text class="history-type">{{ h.type==='player'?'玩家':h.type==='match'?'比赛':'查小号' }}</text>
              </view>
            </view>
          </view>
          <view class="btn btn-primary" @click="searchPlayer"><text>{{ loading?'搜索中...':'搜索比赛' }}</text></view>
        </view>

        <!-- 比赛ID -->
        <view v-else-if="searchMode==='match'" class="search-bar">
          <view class="search-input-wrap">
            <input v-model="matchId" type="number" placeholder="输入比赛ID" class="search-input" @confirm="goDirectMatch" @focus="onInputFocus" @blur="onInputBlur" />
            <view class="history-dropdown" v-if="showHistory && searchHistory.length > 0">
              <view v-for="(h,i) in searchHistory" :key="i" class="history-item" @click="selectHistory(h)">
                <text class="history-label">{{ h.label }}</text>
                <text class="history-type">{{ h.type==='player'?'玩家':h.type==='match'?'比赛':'查小号' }}</text>
              </view>
            </view>
          </view>
          <view class="btn btn-primary" @click="goDirectMatch"><text>❗开庭❗</text></view>
        </view>

        <!-- 捕鱼执法 -->
        <view v-else class="search-bar">
          <view class="search-input-wrap">
            <input v-model="smurfId" type="number" placeholder="输入玩家ID（Steam32 ID）" class="search-input" @confirm="runSmurfCheck" @focus="onInputFocus" @blur="onInputBlur" />
            <view class="history-dropdown" v-if="showHistory && searchHistory.length > 0">
              <view v-for="(h,i) in searchHistory" :key="i" class="history-item" @click="selectHistory(h)">
                <text class="history-label">{{ h.label }}</text>
                <text class="history-type">{{ h.type==='player'?'玩家':h.type==='match'?'比赛':'查小号' }}</text>
              </view>
            </view>
          </view>
          <view class="btn btn-primary" @click="runSmurfCheck"><text>{{ smurfLoading || smurfConfirming ?'检测中...':'检测小号' }}</text></view>
        </view>

        <view v-if="smurfLoading && searchMode==='smurf'" class="smurf-loading">
          <view class="search-spinner"><view class="spin-ring"></view></view>
          <view class="smurf-loading-copy">
            <text class="smurf-loading-title">捕鱼执法中</text>
            <text class="smurf-loading-text">{{ smurfLoadingText }}</text>
            <text class="smurf-loading-hint">首次查询较慢，稍后会快很多</text>
          </view>
          <view class="smurf-progress"><view class="smurf-progress-fill"></view></view>
        </view>

        <view v-if="loading" class="search-loading">
          <view class="search-spinner"><view class="spin-ring"></view></view>
          <text class="search-loading-text">正在调取战绩数据...</text>
        </view>

        <text v-if="error" class="error-msg">{{ error }}</text>

        <!-- 捕鱼结果 -->
        <view v-if="smurfResult && searchMode==='smurf'" class="smurf-result">
          <view class="smurf-score-row">
            <view class="smurf-score-bar">
              <view class="smurf-score-fill" :style="{width: Math.round(smurfResult.score*100)+'%', background: smurfColor(smurfResult.score)}"></view>
            </view>
            <text class="smurf-score-num" :style="{color: smurfColor(smurfResult.score)}">{{ Math.round(smurfResult.score*100) }}%</text>
            <text class="smurf-score-label" :style="{color: smurfColor(smurfResult.score)}">{{ smurfLabel(smurfResult.score) }}</text>
          </view>
          <text class="smurf-roast">{{ smurfResult.roast }}</text>
          <text v-if="smurfCacheHint" class="smurf-cache-hint">{{ smurfCacheHint }}</text>
          <view v-if="smurfExpanded" class="smurf-details">
            <view v-for="s in smurfResult.signals" :key="s.label" class="smurf-signal">
              <view class="signal-header">
                <text class="signal-label">{{ s.label }}</text>
                <text class="signal-value">{{ s.value }}</text>
              </view>
              <view class="signal-bar-bg">
                <view class="signal-bar-fill" :style="{width: Math.round(s.score*100)+'%'}"></view>
              </view>
              <text class="signal-detail">{{ s.detail }}</text>
            </view>
          </view>
          <view class="smurf-toggle" @click="smurfExpanded=!smurfExpanded">
            <text>{{ smurfExpanded ? '收起证据 ▲' : '展开证据 ▼' }}</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="searchMode==='player' && matches.length > 0" class="matches-section">
      <view class="container">
        <text class="section-title">{{ playerName }} 的最近比赛</text>
        <view class="match-grid">
          <view v-for="m in matches" :key="m.match_id" class="match-card" @click="analyzeMatch(m.match_id)">
            <image :src="heroImg(m.hero_icon)" :alt="m.hero_name" class="hero-img" mode="aspectFill" />
            <view class="match-info">
              <text class="match-hero" style="margin-right: 10rpx;">{{ m.hero_name }}</text>
              <text class="match-kda">{{ m.kills }}/{{ m.deaths }}/{{ m.assists }}</text>
              <view class="match-meta">
                <text :class="['tag',m.is_win?'tag-win':'tag-loss']">{{ m.is_win?'WIN':'LOSS' }}</text>
                <text class="match-time">{{ formatDuration(m.duration) }}</text>
                <text class="match-date">{{ formatTime(m.start_time) }}</text>
              </view>
            </view>
            <view class="btn btn-trial" @click.stop="analyzeMatch(m.match_id)"><text>❗开庭❗</text></view>
          </view>
        </view>
      </view>
    </view>
  </view>
  <canvas type="2d" id="shareCanvas" style="position:fixed;left:0;top:0;width:1px;height:1px;opacity:.01;pointer-events:none;z-index:-1"></canvas>
</template>

<style scoped>
.home{position:relative;min-height:100vh}
.home-bg{position:fixed;left:0;top:0;width:100%;height:100vh;z-index:0;filter:blur(1.5px);opacity:.9;transform:scale(1.02)}
.home-mask{position:fixed;left:0;top:0;width:100%;height:100vh;z-index:0;background:linear-gradient(180deg,rgba(17,17,16,.12) 0%,rgba(17,17,16,.48) 100%)}
.hero{position:relative;z-index:1}
.hero{padding:88rpx 0 56rpx;text-align:center}
.hero-title{font-size:68rpx;font-weight:800;margin-bottom:18rpx;color:var(--gold-400);letter-spacing:.04em;display:block;text-shadow:0 4rpx 18rpx rgba(0,0,0,.78)}
.hero-sub{color:#f4ead5;margin-bottom:14rpx;font-size:30rpx;font-weight:600;line-height:2.0;display:block;padding:0 20rpx;text-shadow:0 2rpx 12rpx rgba(0,0,0,.72)}
.hero-sub:last-of-type{margin-bottom:52rpx}
.mode-tabs{display:inline-flex;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:40rpx}
.mode-tab{padding:18rpx 32rpx;font-size:26rpx;font-weight:600;color:var(--text-secondary)}
.mode-tab.active{background:var(--accent);color:var(--on-accent)}
.search-bar{display:flex;gap:24rpx;justify-content:center;align-items:flex-start;flex-wrap:wrap;padding:0 20rpx}
.search-input-wrap{position:relative;flex-shrink:0}
.search-input{width:500rpx;padding:24rpx 32rpx;border-radius:var(--r);border:1px solid var(--border);background:var(--bg-card);color:var(--text-primary);font-size:28rpx;font-weight:500}
.history-dropdown{position:absolute;top:100%;left:0;right:0;margin-top:8rpx;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;z-index:50}
.history-item{display:flex;justify-content:space-between;align-items:center;padding:22rpx 32rpx;border-bottom:1px solid var(--border)}
.history-item:last-child{border-bottom:none}
.history-label{font-size:26rpx;font-weight:600;color:var(--ink-1)}
.history-type{font-size:22rpx;color:var(--ink-3);font-weight:500}
.search-loading{display:flex;align-items:center;justify-content:center;gap:16rpx;margin-top:32rpx}
.search-spinner{width:36rpx;height:36rpx;position:relative}
.spin-ring{width:100%;height:100%;border-radius:50%;border:3rpx solid var(--border);border-top-color:var(--accent);animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.search-loading-text{font-size:24rpx;color:var(--ink-2);font-weight:500}

/* ── 捕鱼 loading ── */
.smurf-loading{display:flex;align-items:center;justify-content:center;gap:20rpx;margin-top:32rpx;padding:24rpx 28rpx;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r)}
.smurf-loading-copy{display:flex;flex-direction:column;align-items:flex-start;gap:4rpx}
.smurf-loading-title{font-size:28rpx;font-weight:800;color:var(--ink-1);letter-spacing:.02em}
.smurf-loading-text{font-size:22rpx;color:var(--ink-2);font-weight:500}
.smurf-loading-hint{font-size:20rpx;color:var(--ink-3);font-weight:400}
.smurf-progress{width:180rpx;height:6rpx;background:var(--panel-2);border-radius:3rpx;overflow:hidden;flex-shrink:0}
.smurf-progress-fill{display:block;width:40%;height:100%;background:var(--accent);border-radius:3rpx;animation:smurf-progress-move 1.3s ease-in-out infinite}
@keyframes smurf-progress-move{0%{transform:translateX(-110%)}50%{transform:translateX(70%)}100%{transform:translateX(220%)}}

.error-msg{color:var(--red-400);margin-top:24rpx;font-size:26rpx;font-weight:500;display:block}
.matches-section{position:relative;z-index:1;padding:48rpx 0 160rpx}
.section-title{font-size:36rpx;font-weight:700;margin-bottom:40rpx;letter-spacing:-.01em;display:block}
.match-grid{display:flex;flex-direction:column;gap:24rpx}
.match-card{display:flex;align-items:center;gap:20rpx;padding:28rpx 32rpx;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r)}
.hero-img{width:120rpx;height:68rpx;border-radius:var(--r-sm);flex-shrink:0}
.match-info{flex:1;min-width:0}
.match-hero{font-weight:600;font-size:28rpx;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.match-kda{font-size:26rpx;color:var(--ink-2);margin:6rpx 0;font-weight:500}
.match-meta{display:flex;align-items:center;gap:16rpx;font-size:22rpx;color:var(--ink-3);font-weight:500}
.match-time,.match-date{color:var(--ink-3)}
.btn{display:inline-flex;align-items:center;gap:12rpx;padding:20rpx 40rpx;border-radius:var(--r-sm);font-size:26rpx;font-weight:600;border:1px solid var(--border);background:var(--bg);color:var(--text-primary)}
.btn-primary{background:var(--accent);border-color:transparent;color:var(--on-accent);font-weight:700}
.btn-trial{padding:14rpx 28rpx;background:var(--accent);color:var(--on-accent);border-radius:var(--r-sm);font-size:24rpx;font-weight:800;flex-shrink:0;letter-spacing:.04em}
.tag{display:inline-flex;align-items:center;padding:4rpx 16rpx;border-radius:var(--r-sm);font-size:22rpx;font-weight:700;letter-spacing:.03em}
.tag-win{background:rgba(63,185,80,.1);color:var(--green-400)}
.tag-loss{background:rgba(248,81,73,.1);color:var(--red-400)}
.container{padding:0 32rpx}

/* ── 捕鱼结果 ── */
.smurf-result{margin-top:40rpx;padding:32rpx;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);text-align:left}
.smurf-score-row{display:flex;align-items:center;gap:16rpx;margin-bottom:20rpx}
.smurf-score-bar{flex:1;height:12rpx;background:var(--panel-2);border-radius:6rpx;overflow:hidden}
.smurf-score-fill{height:100%;border-radius:6rpx}
.smurf-score-num{font-size:36rpx;font-weight:800;min-width:80rpx;text-align:right}
.smurf-score-label{font-size:22rpx;font-weight:700;background:rgba(255,255,255,.05);padding:4rpx 16rpx;border-radius:var(--r-sm)}
.smurf-roast{font-size:26rpx;color:var(--ink-2);line-height:1.6;font-style:italic;margin-bottom:16rpx;display:block}
.smurf-cache-hint{font-size:22rpx;color:var(--accent);margin:-8rpx 0 16rpx;display:block}
.smurf-details{margin-top:16rpx}
.smurf-signal{margin-bottom:16rpx}
.signal-header{display:flex;justify-content:space-between;font-size:24rpx;margin-bottom:6rpx}
.signal-label{color:var(--ink-3);font-weight:500}
.signal-value{color:var(--ink-2);font-weight:600}
.signal-bar-bg{height:6rpx;background:var(--panel-2);border-radius:3rpx;overflow:hidden;margin-bottom:4rpx}
.signal-bar-fill{height:100%;background:var(--accent);border-radius:3rpx}
.signal-detail{font-size:20rpx;color:var(--ink-3)}
.smurf-toggle{margin-top:20rpx;text-align:center}
.smurf-toggle text{font-size:24rpx;color:var(--accent);font-weight:600}
</style>
