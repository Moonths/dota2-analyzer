<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '../../api/index.js'
import { drawShareCard } from '../../utils/shareImage.js'
import PlayerCard from '../../components/PlayerCard.vue'
import PositionEval from '../../components/PositionEval.vue'
import Timeline from '../../components/Timeline.vue'

const matchId = ref('')
const result = ref(null)
const loading = ref(true)
const error = ref('')
const limitReached = ref(false)
const activeTeam = ref('radiant')
const loadingText = ref('正在查阅比赛录像...')

// ── 小号检测 ──
const smurfChecking = ref(false)
const smurfConfirming = ref(false)
const smurfResult = ref(null)
const smurfError = ref('')
const smurfExpanded = ref(false)
const shareImagePath = ref('')
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

const loadingTexts = ['正在查阅比赛录像...','正在比对英雄数据...','正在分析装备路线...','正在甄别战犯与功臣...','正在撰写判词...']
let _textTimer = null
let _textIndex = 0

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

onLoad((options) => {
  matchId.value = options.matchId
  promptBeforeAnalyze(options.provider || undefined, options.model || undefined)
})

onUnmounted(() => {
  if (_textTimer) clearInterval(_textTimer)
  endSmurfLoading()
})

function showQuotaModal(remaining, kind = 'analysis') {
  const label = kind === 'analysis' ? '比赛分析' : '小号检测'
  const isExhaustedAnalysis = kind === 'analysis' && remaining <= 0
  return new Promise((resolve) => {
    uni.showModal({
      title: '今日分析机会',
      content: isExhaustedAnalysis
        ? '今天 3 次新分析机会已用完，已分析过的比赛仍可直接查看。是否继续？'
        : `本次${label}会消耗 1 次机会，今天还剩 ${remaining} 次。`,
      confirmText: isExhaustedAnalysis ? '继续查看' : (kind === 'analysis' ? '继续分析' : '继续检测'),
      cancelText: '先不',
      success: (res) => resolve(!!res.confirm),
      fail: () => resolve(false),
    })
  })
}

async function promptBeforeAnalyze(provider, model) {
  try {
    const quota = await api.getQuota()
    const remaining = quota && typeof quota.remaining === 'number'
      ? quota.remaining
      : (quota && typeof quota.analysis_remaining === 'number' ? quota.analysis_remaining : 0)
    loading.value = false
    const confirmed = await showQuotaModal(remaining, 'analysis')
    if (confirmed) {
      doAnalyze(provider, model)
    } else {
      goHome()
    }
  } catch (e) {
    // 额度查询失败时不阻断分析，由分析接口最终兜底。
    doAnalyze(provider, model)
  }
}

async function doAnalyze(provider, model) {
  _textTimer = setInterval(() => { _textIndex = (_textIndex + 1) % loadingTexts.length; loadingText.value = loadingTexts[_textIndex] }, 2500)
  try {
    loading.value = true
    result.value = await api.analyze(parseInt(matchId.value), provider, model)
    if (result.value) {
      activeTeam.value = result.value.radiant_win ? 'dire' : 'radiant'
      drawShareCard(result.value.scapegoat, result.value.mvp).then(p => { shareImagePath.value = p })
    }
  } catch (e) {
    const msg = e.message || '分析失败'
    if (msg.includes('429') || msg.includes('用完') || msg.includes('明天再来')) {
      limitReached.value = true
      uni.showToast({ title: '今天 3 次分析机会已用完，明天再来！', icon: 'none', duration: 2500 })
    } else { error.value = msg }
  } finally { loading.value = false; if (_textTimer) { clearInterval(_textTimer); _textTimer = null } }
}

const filteredEvals = computed(() => {
  if (!result.value || !result.value.position_evals) return []
  const isRadiant = activeTeam.value === 'radiant'
  const cards = isRadiant ? result.value.radiant_players : result.value.dire_players
  if (!cards || !cards.length) return []
  const teamEvals = (result.value.position_evals||[]).filter(e => e.is_radiant === isRadiant)
  return cards.map((card,i) => {
    const pe = teamEvals[i]
    return pe ? {...pe, _card:card} : null
  }).filter(Boolean)
})

function copyShareUrl() {
  uni.showToast({ title: "请点击右上角「...」分享给朋友", icon: "none", duration: 2000 })
}

function smurfLabel(score){if(score>=0.85)return'极高';if(score>=0.70)return'很高';if(score>=0.55)return'较高';if(score>=0.40)return'中等';return'较低'}
function smurfColor(score){if(score>=0.70)return'var(--down)';if(score>=0.55)return'var(--warn)';if(score>=0.40)return'var(--accent)';return'var(--up)'}

async function checkSmurf() {
  const now = Date.now()
  if(smurfChecking.value || smurfConfirming.value || now - smurfLastRunAt < 600)return
  const aid = result.value?.mvp?.account_id
  if(!aid){smurfError.value='无法获取MVP的玩家ID';return}

  smurfLastRunAt = now
  smurfConfirming.value = true
  try {
    const quota = await api.getQuota()
    const remaining = quota && typeof quota.remaining === 'number'
      ? quota.remaining
      : (quota && typeof quota.analysis_remaining === 'number' ? quota.analysis_remaining : 0)
    if (remaining <= 0) {
      uni.showToast({ title: '今天 3 次分析机会已用完，明天再来！', icon: 'none', duration: 2500 })
      return
    }
    if (!(await showQuotaModal(remaining, 'smurf'))) return
  } catch (e) {
    // 额度查询失败时不阻断，由后端接口最终兜底。
  } finally {
    smurfConfirming.value = false
  }

  const seq = ++smurfRequestSeq
  smurfChecking.value=true;smurfError.value='';smurfResult.value=null;smurfExpanded.value=false
  beginSmurfLoading()
  try {
    const result = await api.smurfCheck(aid)
    if (seq === smurfRequestSeq) smurfResult.value = result
  } catch(e) {
    if (seq === smurfRequestSeq) smurfError.value = e.message || '检测失败'
  } finally {
    if (seq === smurfRequestSeq) {
      endSmurfLoading()
      smurfChecking.value = false
    }
  }
}

function formatDuration(sec) { const m=Math.floor(sec/60); const s=sec%60; return `${m}:${s.toString().padStart(2,'0')}` }
function goHome() { uni.navigateBack() }

function onShareAppMessage() {
  if (!result.value) return { title: '分锅大会 — AI判官为你揭晓战犯', path: '/pages/index/index' }
  const sg = result.value.scapegoat
  return {
    title: `🤡 ${sg.player_name}(${sg.hero_name}) 荣获本场背锅侠！KDA ${sg.kda}`,
    path: `/pages/analysis/analysis?matchId=${matchId.value}`,
    imageUrl: shareImagePath.value || '',
  }
}
</script>

<template>
  <view class="analysis-page">
    <view v-if="loading" class="loading-state"><view class="loading-scene">
      <view class="crest-ring"><view class="crest-inner"><text class="crest-icon">⚔️</text></view><view class="ring-arc"></view></view>
      <text class="loading-title">AI 判官升堂中</text>
      <text class="loading-hint">{{ loadingText }}</text>
      <view class="progress-wrap"><view class="progress-bar"><view class="progress-fill"></view></view></view>
      <text class="loading-patience">局势复杂，请耐心等候...</text>
    </view></view>

    <view v-else-if="limitReached" class="error-state container"><text class="limit-icon">⏳</text><text class="error-msg">今天 3 次分析机会已用完</text><text class="limit-hint">已分析过的比赛仍可直接查看</text><view class="btn btn-back" @click="goHome"><text>返回首页</text></view></view>
    <view v-else-if="error" class="error-state container"><text class="error-msg">{{ error }}</text><view class="btn btn-back" @click="goHome"><text>返回首页</text></view></view>

    <template v-else-if="result">
      <view class="container">
        <view class="match-overview"><view class="overview-left"><text class="match-id">Match #{{ result.match_id }}</text><text class="match-skill">{{ result.skill_level }}</text><text class="match-duration">{{ formatDuration(result.duration) }}</text></view><view class="overview-right"><view class="btn btn-sm" @click="copyShareUrl"><text>分享</text></view></view></view>
        <text v-if="result.game_summary" class="game-summary">{{ result.game_summary }}</text>
        <view class="hero-cards">
          <view class="hero-card sg-card"><view class="card-badge sg-badge"><text>🤡 背锅侠</text></view><PlayerCard :player="result.scapegoat" /><text class="card-reason">{{ result.scapegoat.reason }}</text></view>
          <view class="hero-card mvp-card"><view class="card-badge mvp-badge"><text>🏆 MVP</text></view><PlayerCard :player="result.mvp" /><text class="card-reason">{{ result.mvp.reason }}</text><view class="smurf-action"><view class="smurf-btn" @click="checkSmurf"><text>🔍 {{ smurfChecking || smurfConfirming ?'检测中...':'这人是小号吗？' }}</text></view><view v-if="smurfChecking || smurfConfirming" class="smurf-checking"><view class="smurf-checking-spinner"></view><text>{{ smurfLoadingText }}</text></view><text v-if="smurfError" class="smurf-error-inline">{{ smurfError }}</text></view><view v-if="smurfResult" class="smurf-inline"><view class="smurf-inline-score"><text class="smurf-inline-num" :style="{color:smurfColor(smurfResult.score)}">{{ Math.round(smurfResult.score*100) }}%</text><text class="smurf-inline-label" :style="{color:smurfColor(smurfResult.score)}">{{ smurfLabel(smurfResult.score) }}</text></view><text class="smurf-inline-roast">{{ smurfResult.roast }}</text><view v-if="smurfExpanded" class="smurf-inline-details"><view v-for="s in smurfResult.signals" :key="s.label" class="smurf-inline-signal"><text class="sis-label">{{ s.label }}</text><text class="sis-value">{{ s.value }}</text></view></view><view class="smurf-toggle" @click="smurfExpanded=!smurfExpanded"><text>{{ smurfExpanded?'收起 ▲':'展开 ▼' }}</text></view></view></view>
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
    <canvas type="2d" id="shareCanvas" style="position:fixed;left:-9999px;top:0;width:250px;height:200px"></canvas>
  </view>
</template>

<style scoped>
.analysis-page{padding:60rpx 0 120rpx}
.loading-state{display:flex;flex-direction:column;align-items:center;padding:120rpx 40rpx 0}
.loading-scene{display:flex;flex-direction:column;align-items:center;gap:32rpx}
.crest-ring{position:relative;width:140rpx;height:140rpx;display:flex;align-items:center;justify-content:center}
.crest-inner{width:100rpx;height:100rpx;border-radius:50%;background:var(--bg-card);border:2rpx solid var(--border);display:flex;align-items:center;justify-content:center;z-index:2}
.crest-icon{font-size:44rpx;animation:crest-pulse 2s ease-in-out infinite}
@keyframes crest-pulse{0%,100%{transform:scale(1);opacity:.8}50%{transform:scale(1.08);opacity:1}}
.ring-arc{position:absolute;top:0;left:0;right:0;bottom:0;border-radius:50%;border:3rpx solid transparent;border-top-color:var(--accent);border-right-color:var(--accent);animation:ring-spin 1.5s linear infinite}
@keyframes ring-spin{to{transform:rotate(360deg)}}
.loading-title{font-size:36rpx;font-weight:800;color:var(--ink-1);letter-spacing:.04em}
.loading-hint{font-size:26rpx;color:var(--ink-2);font-weight:500}
.progress-wrap{width:400rpx;height:6rpx;background:var(--panel-2);border-radius:3rpx;overflow:hidden}
.progress-bar{width:100%;height:100%}
.progress-fill{height:100%;width:30%;background:var(--accent);border-radius:3rpx;animation:progress-creep 4s ease-in-out infinite}
@keyframes progress-creep{0%{width:5%}50%{width:75%}100%{width:5%}}
.loading-patience{font-size:22rpx;color:var(--ink-3);margin-top:8rpx}
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
.smurf-action{margin-top:28rpx;padding-top:24rpx;border-top:1px solid var(--border)}
.smurf-btn{display:inline-flex;align-items:center;padding:14rpx 28rpx;border:1px solid var(--border);border-radius:var(--r-sm);font-size:24rpx;color:var(--ink-2);font-weight:600}
.smurf-checking{display:flex;align-items:center;gap:10rpx;margin-top:14rpx;font-size:22rpx;color:var(--ink-2)}
.smurf-checking-spinner{width:20rpx;height:20rpx;border:3rpx solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:smurf-inline-spin .8s linear infinite}
@keyframes smurf-inline-spin{to{transform:rotate(360deg)}}
.smurf-error-inline{font-size:22rpx;color:var(--red-400);margin-top:12rpx;display:block}
.smurf-inline{margin-top:20rpx}
.smurf-inline-score{display:flex;align-items:center;gap:12rpx;margin-bottom:8rpx}
.smurf-inline-num{font-size:32rpx;font-weight:800}
.smurf-inline-label{font-size:20rpx;font-weight:700;background:rgba(255,255,255,.05);padding:2rpx 12rpx;border-radius:var(--r-sm)}
.smurf-inline-roast{font-size:24rpx;color:var(--ink-2);line-height:1.6;font-style:italic;margin-bottom:12rpx;display:block}
.smurf-inline-details{display:flex;flex-wrap:wrap;gap:8rpx 20rpx;margin-bottom:10rpx}
.smurf-inline-signal{display:flex;align-items:center;gap:6rpx;font-size:22rpx}
.sis-label{color:var(--ink-3)}
.sis-value{color:var(--ink-2);font-weight:700}
.smurf-toggle text{font-size:22rpx;color:var(--accent);font-weight:600}
.container{padding:0 32rpx}
</style>
