<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '../../api/index.js'
import PlayerCard from '../../components/PlayerCard.vue'
import PositionEval from '../../components/PositionEval.vue'
import Timeline from '../../components/Timeline.vue'

const shareId = ref('')
const result = ref(null)
const loading = ref(true)
const error = ref('')
const activeTeam = ref('radiant')

onLoad((options) => { shareId.value = options.shareId; loadShare() })

async function loadShare() {
  try {
    result.value = await api.getSharedAnalysis(shareId.value)
    if (result.value) activeTeam.value = result.value.radiant_win ? 'dire' : 'radiant'
  } catch (e) { error.value = e.message || '加载失败' }
  finally { loading.value = false }
}

const filteredEvals = computed(() => {
  if (!result.value || !result.value.position_evals) return []
  const cards = activeTeam.value === 'radiant' ? result.value.radiant_players : result.value.dire_players
  if (!cards || !cards.length) return []
  const evals = result.value.position_evals || []
  return cards.map(card => {
    const pe = evals.find(e => e.player_name === card.player_name) || evals.find(e => e.position === card.position)
    return pe ? { ...pe, _card: card } : null
  }).filter(Boolean)
})

function formatDuration(sec) { const m = Math.floor(sec / 60); const s = sec % 60; return `${m}:${s.toString().padStart(2, '0')}` }
function goHome() { uni.navigateBack() }
</script>

<template>
  <view class="analysis-page">
    <view v-if="loading" class="loading-state"><view class="spinner"></view><text>加载分享内容...</text></view>
    <view v-else-if="error" class="error-state container"><text class="error-msg">{{ error }}</text><view class="btn btn-primary" @click="goHome"><text>返回首页</text></view></view>
    <template v-else-if="result">
      <view class="container">
        <view class="match-overview">
          <view class="overview-left"><text class="match-id">Match #{{ result.match_id }}</text><text class="match-skill">{{ result.skill_level }}</text><text class="match-duration">{{ formatDuration(result.duration) }}</text></view>
          <view class="overview-right"><text class="shared-badge">分享的分析</text></view>
        </view>
        <text v-if="result.game_summary" class="game-summary">{{ result.game_summary }}</text>
        <view class="hero-cards">
          <view class="hero-card sg-card"><view class="card-badge sg-badge"><text>🤡 背锅侠</text></view><PlayerCard :player="result.scapegoat" /><text class="card-reason">{{ result.scapegoat.reason }}</text></view>
          <view class="hero-card mvp-card"><view class="card-badge mvp-badge"><text>🏆 MVP</text></view><PlayerCard :player="result.mvp" /><text class="card-reason">{{ result.mvp.reason }}</text></view>
        </view>
        <view class="team-tabs">
          <view :class="['team-tab','radiant',{active:activeTeam==='radiant'}]" @click="activeTeam='radiant'"><view class="team-dot radiant-dot"><view class="dot-inner"></view></view><text>天辉</text><text v-if="result.radiant_win" class="crown">WIN</text></view>
          <view :class="['team-tab','dire',{active:activeTeam==='dire'}]" @click="activeTeam='dire'"><view class="team-dot dire-dot"><view class="dot-inner"></view></view><text>夜魇</text><text v-if="!result.radiant_win" class="crown">WIN</text></view>
        </view>
        <view class="position-grid"><PositionEval v-for="pe in filteredEvals" :key="pe._card.position+'_'+activeTeam" :eval="pe" :playerCard="pe._card" /></view>
        <text class="section-title">关键事件</text>
        <Timeline :events="result.timeline" />
      </view>
    </template>
  </view>
</template>

<style scoped>
.analysis-page{padding:60rpx 0 120rpx}
.loading-state{display:flex;flex-direction:column;align-items:center;padding:160rpx 40rpx;gap:32rpx;color:var(--text-secondary);font-size:28rpx}
.spinner{width:72rpx;height:72rpx;border:6rpx solid var(--border);border-top-color:var(--gold);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.error-state{text-align:center;padding:120rpx 40rpx}
.error-msg{color:var(--red);margin-bottom:32rpx;font-size:28rpx;display:block}
.match-overview{display:flex;justify-content:space-between;align-items:center;padding:32rpx 40rpx;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);margin-bottom:40rpx}
.overview-left{display:flex;gap:16rpx;align-items:center;font-size:26rpx;color:var(--text-secondary);flex:1;min-width:0}
.overview-right{flex-shrink:0;white-space:nowrap;margin-left:16rpx}
.match-id{font-weight:700;color:var(--text-primary);font-size:28rpx;white-space:nowrap;flex-shrink:0}
.match-skill{background:var(--accent-soft);color:var(--accent);padding:4rpx 20rpx;border-radius:var(--r-sm);font-size:22rpx;font-weight:600;letter-spacing:.03em;white-space:nowrap;flex-shrink:0}
.match-duration{color:var(--ink-3);font-size:24rpx;white-space:nowrap;flex-shrink:0}
.shared-badge{font-size:24rpx;color:var(--ink-3);font-weight:500}
.game-summary{text-align:center;font-size:30rpx;color:var(--text-secondary);font-style:italic;padding:32rpx 0 48rpx;border-bottom:1px solid var(--border);margin-bottom:56rpx;line-height:1.6;display:block}
.hero-cards{display:flex;flex-direction:column;gap:40rpx;margin-bottom:64rpx}
.hero-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:48rpx;position:relative}
.mvp-card{border-color:var(--accent);background:rgba(212,168,67,.04)}
.sg-card{border-color:rgba(248,81,73,.35);background:rgba(248,81,73,.04);box-shadow:0 0 32rpx rgba(248,81,73,.08)}
.card-badge{position:absolute;top:-24rpx;left:40rpx;padding:8rpx 28rpx;border-radius:var(--r-sm);font-size:22rpx;font-weight:800;letter-spacing:.04em}
.mvp-badge{background:var(--accent);color:var(--on-accent)}
.sg-badge{position:absolute;top:24rpx;right:24rpx;left:auto;transform:rotate(-14deg);padding:16rpx 30rpx;font-size:34rpx;font-weight:900;color:#fff;background:#d93d36;border:5rpx double #ffe0d0;border-radius:12rpx;letter-spacing:.12em;line-height:1.15;opacity:.9;z-index:5;box-shadow:2rpx 4rpx 16rpx rgba(217,61,54,.35)}
.card-reason{margin-top:28rpx;font-size:26rpx;color:var(--ink-2);line-height:1.6}
.team-tabs{display:flex;gap:0;margin-bottom:36rpx;border-bottom:2px solid var(--border)}
.team-tab{flex:1;padding:24rpx 0 20rpx;font-size:28rpx;font-weight:700;display:flex;align-items:center;justify-content:center;gap:10rpx;color:var(--ink-3);position:relative;transition:color .2s}
.team-tab.radiant{color:rgba(63,185,80,.4)}.team-tab.dire{color:rgba(248,81,73,.4)}
.team-tab.radiant.active{color:var(--green-400);border-bottom:3px solid var(--green-400);margin-bottom:-2px}
.team-tab.dire.active{color:var(--red-400);border-bottom:3px solid var(--red-400);margin-bottom:-2px}
.team-dot{width:16rpx;height:16rpx;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.radiant-dot{background:rgba(63,185,80,.15)}.dire-dot{background:rgba(248,81,73,.15)}
.dot-inner{width:8rpx;height:8rpx;border-radius:50%;background:transparent}
.team-tab.radiant .radiant-dot .dot-inner{background:rgba(63,185,80,.5)}
.team-tab.dire .dire-dot .dot-inner{background:rgba(248,81,73,.5)}
.team-tab.radiant.active .radiant-dot{background:rgba(63,185,80,.35)}
.team-tab.radiant.active .radiant-dot .dot-inner{background:var(--green-400)}
.team-tab.dire.active .dire-dot{background:rgba(248,81,73,.35)}
.team-tab.dire.active .dire-dot .dot-inner{background:var(--red-400)}
.crown{font-size:18rpx;font-weight:800;padding:2rpx 10rpx;border-radius:8rpx;letter-spacing:.06em;background:transparent;color:var(--ink-3)}
.team-tab.radiant.active .crown{background:rgba(63,185,80,.2);color:var(--green-400)}
.team-tab.dire.active .crown{background:rgba(248,81,73,.2);color:var(--red-400)}
.section-title{font-weight:700;margin:64rpx 0 32rpx;color:var(--ink-2);text-transform:uppercase;font-size:22rpx;letter-spacing:.06em;display:block}
.position-grid{display:flex;flex-direction:column;gap:20rpx;margin-bottom:16rpx}
.btn{display:inline-flex;align-items:center;gap:12rpx;padding:20rpx 40rpx;border-radius:var(--r-sm);font-size:26rpx;font-weight:600;border:1px solid var(--border);background:var(--bg);color:var(--text-primary);white-space:nowrap}
.btn-primary{background:var(--accent);border-color:transparent;color:var(--on-accent);font-weight:700}
.container{padding:0 32rpx}
</style>
