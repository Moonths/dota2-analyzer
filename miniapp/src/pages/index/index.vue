<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/index.js'
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
const shareImage = ref()

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
  else { searchMode.value = 'match'; matchId.value = item.value }
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

function onShareAppMessage() {
  return {
    imageUrl: shareImagePath.value, title: '分锅大会 —— 谁尽力谁犯罪，AI判官为你揭晓',
    path: '/pages/index/index',
  }
}
  const val = matchId.value.trim()
  const id = parseInt(val)
  if (!id) { error.value = '请输入有效的比赛ID'; return }
  saveHistory('match', val, `比赛 ${val}`)
  showHistory.value = false
  analyzeMatch(id)
}

function onInputFocus() { showHistory.value = searchHistory.value.length > 0 }
function onInputBlur() { setTimeout(() => { showHistory.value = false }, 200) }

function formatDuration(sec) { const m = Math.floor(sec / 60); const s = sec % 60; return `${m}:${s.toString().padStart(2, '0')}` }
function formatTime(ts) { return new Date(ts * 1000).toLocaleDateString('zh-CN') }
</script>

<template>
  <view class="home">
    <view class="hero">
      <view class="container">
        <text class="hero-title">谁尽力 谁犯罪</text>
        <text class="hero-title" style="font-size:56rpx;">谁的打法不团队</text>
        <text class="hero-sub">谁在see 谁针对 是谁野区把线对</text>
        <text class="hero-sub">谁勇敢 谁暴毙 又是谁没人情味？</text>

        <view class="mode-tabs">
          <view :class="['mode-tab',{active:searchMode==='player'}]" @click="searchMode='player'"><text>搜玩家找比赛</text></view>
          <view :class="['mode-tab',{active:searchMode==='match'}]" @click="searchMode='match'"><text>直接输入比赛ID</text></view>
        </view>

        <view v-if="searchMode==='player'" class="search-bar">
          <view class="search-input-wrap">
            <input v-model="playerId" type="number" placeholder="输入 Dota 2 玩家ID（Steam32 ID）" class="search-input" @confirm="searchPlayer" @focus="onInputFocus" @blur="onInputBlur" />
            <view class="history-dropdown" v-if="showHistory && searchHistory.length > 0">
              <view v-for="(h,i) in searchHistory" :key="i" class="history-item" @click="selectHistory(h)">
                <text class="history-label">{{ h.label }}</text>
                <text class="history-type">{{ h.type==='player'?'玩家':'比赛' }}</text>

        <view v-if="loading" class="search-loading">
          <view class="search-spinner"><view class="spin-ring"></view></view>
          <text class="search-loading-text">正在调取战绩数据...</text>
        </view>
              </view>
            </view>
          </view>
          <view class="btn btn-primary" @click="searchPlayer"><text>{{ loading?'搜索中...':'搜索比赛' }}</text></view>
        </view>

        <view v-else class="search-bar">
          <view class="search-input-wrap">
            <input v-model="matchId" type="number" placeholder="输入比赛ID" class="search-input" @confirm="goDirectMatch" @focus="onInputFocus" @blur="onInputBlur" />
            <view class="history-dropdown" v-if="showHistory && searchHistory.length > 0">
              <view v-for="(h,i) in searchHistory" :key="i" class="history-item" @click="selectHistory(h)">
                <text class="history-label">{{ h.label }}</text>
                <text class="history-type">{{ h.type==='player'?'玩家':'比赛' }}</text>
              </view>
            </view>
          </view>
          <view class="btn btn-primary" @click="goDirectMatch"><text>❗开庭❗</text></view>
        </view>

        <text v-if="error" class="error-msg">{{ error }}</text>
      </view>
    </view>

    <view v-if="searchMode==='player' && matches.length > 0" class="matches-section">
      <view class="container">
        <text class="section-title">{{ playerName }} 的最近比赛</text>
        <view class="match-grid">
          <view v-for="m in matches" :key="m.match_id" class="match-card" @click="analyzeMatch(m.match_id)">
            <image :src="m.hero_icon" :alt="m.hero_name" class="hero-img" mode="aspectFill" />
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
  <canvas canvas-id="shareCanvas" style="position:fixed;left:-9999px;top:0;width:250px;height:200px"></canvas>
</template>

<style scoped>
.hero{padding:88rpx 0 56rpx;text-align:center}
.hero-title{font-size:68rpx;font-weight:800;margin-bottom:18rpx;color:var(--ink-1);letter-spacing:.04em;display:block}
.hero-sub{color:var(--text-secondary);margin-bottom:14rpx;font-size:30rpx;font-weight:500;line-height:2.0;display:block;padding:0 20rpx}
.hero-sub:last-of-type{margin-bottom:52rpx}
.mode-tabs{display:inline-flex;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:40rpx}
.mode-tab{padding:18rpx 44rpx;font-size:26rpx;font-weight:600;color:var(--text-secondary)}
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

.error-msg{color:var(--red-400);margin-top:24rpx;font-size:26rpx;font-weight:500;display:block}
.matches-section{padding:48rpx 0 160rpx}
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
</style>
