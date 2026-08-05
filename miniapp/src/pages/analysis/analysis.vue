<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '../../api/index.js'
import PlayerCard from '../../components/PlayerCard.vue'
import PositionEval from '../../components/PositionEval.vue'
import Timeline from '../../components/Timeline.vue'

const matchId = ref('')
const result = ref(null)
const loading = ref(true)
const error = ref('')
const limitReached = ref(false)
const shareCopied = ref(false)
const activeTeam = ref('radiant')

onLoad((options) => {
  matchId.value = options.matchId
  const provider = options.provider || undefined
  const model = options.model || undefined
  doAnalyze(provider, model)
})

async function doAnalyze(provider, model) {
  try {
    loading.value = true
    result.value = await api.analyze(parseInt(matchId.value), provider, model)
    if (result.value) activeTeam.value = result.value.radiant_win ? 'dire' : 'radiant'
  } catch (e) {
    const msg = e.message || '分析失败'
    if (msg.includes('429') || msg.includes('用完') || msg.includes('明天再来')) {
      limitReached.value = true
      uni.showToast({ title: '今天的新分析次数已用完，明天再来！', icon: 'none', duration: 2500 })
    } else {
      error.value = msg
    }
  } finally { loading.value = false }
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

function copyShareUrl() {
  if (!result.value || !result.value.share_url) return
  uni.setClipboardData({ data: result.value.share_url, success() { shareCopied.value = true; setTimeout(() => { shareCopied.value = false }, 2000) } })
}

function formatDuration(sec) { const m = Math.floor(sec / 60); const s = sec % 60; return `${m}:${s.toString().padStart(2, '0')}` }
function goHome() { uni.navigateBack() }
</script>

<template>
  <view class="analysis-page">
    <view v-if="loading" class="loading-state">
      <view class="judge-scene">
        <view class="gavel-wrap">
          <text class="gavel">🔨</text>
          <view class="gavel-shadow"></view>
        </view>
        <text class="loading-title">AI 判官升堂中...</text>
        <text class="loading-sub">正在审查比赛数据，甄别战犯与功臣</text>
        <view class="loading-dots">
          <view class="dot" v-for="i in 3" :key="i" :style="{animationDelay: (i-1)*0.2+'s'}"></view>
        </view>
      </view>
    </view>

    <view v-else-if="limitReached" class="error-state container">
      <text class="limit-icon">⏳</text>
      <text class="error-msg">今天的新分析次数已用完</text>
      <text class="limit-hint">已分析过的比赛不受限制，可直接从玩家列表进入</text>
      <view class="btn btn-back" @click="goHome"><text>返回首页</text></view>
    </view>

    <view v-else-if="error" class="error-state container">
      <text class="error-msg">{{ error }}</text>
      <view class="btn btn-back" @click="goHome"><text>返回首页</text></view>
    </view>

    <template v-else-if="result">
      <view class="container">
        <view class="match-overview">
          <view class="overview-left">
            <text class="match-id">Match #{{ result.match_id }}</text>
            <text class="match-skill">{{ result.skill_level }}</text>
            <text class="match-duration">{{ formatDuration(result.duration) }}</text>
          </view>
          <view class="overview-right">
            <view class="btn btn-sm" @click="copyShareUrl"><text>{{ shareCopied ? '已复制!' : '分享链接' }}</text></view>
          </view>
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

/* Loading - Judge scene */
.loading-state{display:flex;flex-direction:column;align-items:center;padding:160rpx 40rpx 0}
.judge-scene{display:flex;flex-direction:column;align-items:center;gap:28rpx}
.gavel-wrap{position:relative;width:120rpx;height:140rpx;display:flex;align-items:center;justify-content:center}
.gavel{font-size:80rpx;animation:gavel-slam .6s ease-in-out infinite alternate;transform-origin:bottom right}
@keyframes gavel-slam{0%{transform:rotate(-30deg)}100%{transform:rotate(5deg)}}
.gavel-shadow{position:absolute;bottom:0;width:40rpx;height:8rpx;background:rgba(0,0,0,.3);border-radius:50%;animation:shadow-pulse .6s ease-in-out infinite alternate}
@keyframes shadow-pulse{0%{transform:scaleX(1);opacity:.3}100%{transform:scaleX(.5);opacity:.1}}
.loading-title{font-size:36rpx;font-weight:800;color:var(--ink-1);letter-spacing:.02em}
.loading-sub{font-size:26rpx;color:var(--ink-2);font-weight:500}
.loading-dots{display:flex;gap:16rpx;margin-top:8rpx}
.dot{width:10rpx;height:10rpx;border-radius:50%;background:var(--accent);animation:dot-bounce .6s ease-in-out infinite}
@keyframes dot-bounce{0%,100%{opacity:.3;transform:translateY(0)}50%{opacity:1;transform:translateY(-12rpx)}}

/* Error states */
.error-state{text-align:center;padding:160rpx 40rpx 120rpx}
.error-msg{color:var(--red);margin-bottom:24rpx;font-size:28rpx;display:block}
.limit-icon{font-size:80rpx;display:block;margin-bottom:24rpx}
.limit-hint{color:var(--ink-3);font-size:24rpx;display:block;margin-bottom:32rpx;line-height:1.6}
.btn-back{display:inline-flex;align-items:center;padding:20rpx 48rpx;border-radius:var(--r-sm);font-size:26rpx;font-weight:600;border:1px solid var(--border);background:var(--bg);color:var(--text-primary)}

.match-overview{display:flex;justify-content:space-between;align-items:center;padding:32rpx 40rpx;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);margin-bottom:40rpx}
.overview-left{display:flex;gap:16rpx;align-items:center;font-size:26rpx;color:var(--text-secondary);flex:1;min-width:0}
.overview-right{flex-shrink:0;white-space:nowrap;margin-left:16rpx}
.match-id{font-weight:700;color:var(--text-primary);font-size:28rpx;white-space:nowrap;flex-shrink:0}
.match-skill{background:var(--accent-soft);color:var(--accent);padding:4rpx 20rpx;border-radius:var(--r-sm);font-size:22rpx;font-weight:600;letter-spacing:.03em;white-space:nowrap;flex-shrink:0}
.match-duration{color:var(--ink-3);font-size:24rpx;white-space:nowrap;flex-shrink:0}
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
.btn-sm{padding:12rpx 28rpx;font-size:24rpx;border-radius:var(--r-sm);display:inline-flex;align-items:center;border:1px solid var(--border);background:var(--bg);color:var(--text-primary);font-weight:600;white-space:nowrap;flex-shrink:0}
.container{padding:0 32rpx}
</style>
