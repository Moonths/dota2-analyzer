<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type AnalysisResult, type SmurfResult } from '../api'
import PlayerCard from '../components/PlayerCard.vue'
import PositionEval from '../components/PositionEval.vue'
import Timeline from '../components/Timeline.vue'

const props = defineProps<{ matchId: string }>()
const route = useRoute()
const router = useRouter()

const result = ref<AnalysisResult | null>(null)
const loading = ref(true)
const error = ref('')
const shareCopied = ref(false)
const activeTeam = ref<'radiant' | 'dire'>('radiant')

// ── 小号检测 ──
const smurfChecking = ref(false)
const smurfConfirming = ref(false)
const smurfResult = ref<SmurfResult | null>(null)
const smurfError = ref('')
const smurfExpanded = ref(false)
const smurfLoadingText = ref('正在调取玩家战绩...')
const smurfLoadingTexts = [
  '正在调取玩家战绩...',
  '正在逐场核对比赛数据...',
  '正在比对英雄基准...',
  '正在给这条鱼定罪...',
]
let smurfTextTimer: number | undefined
let smurfTextIndex = 0
let smurfRequestSeq = 0
let smurfLastRunAt = 0

function beginSmurfLoading() {
  smurfTextIndex = 0
  smurfLoadingText.value = smurfLoadingTexts[0]
  smurfTextTimer = window.setInterval(() => {
    smurfTextIndex = (smurfTextIndex + 1) % smurfLoadingTexts.length
    smurfLoadingText.value = smurfLoadingTexts[smurfTextIndex]
  }, 1600)
}

function endSmurfLoading() {
  if (smurfTextTimer) {
    window.clearInterval(smurfTextTimer)
    smurfTextTimer = undefined
  }
}

onUnmounted(endSmurfLoading)

async function confirmAnalysisQuota(): Promise<boolean> {
  try {
    const quota = await api.getQuota()
    const remaining = quota?.remaining ?? quota?.analysis_remaining ?? 0
    const message = remaining > 0
      ? `本次比赛分析会消耗 1 次机会，今天还剩 ${remaining} 次。确定继续吗？`
      : '今天 3 次新分析机会已用完，已分析过的比赛仍可直接查看。是否继续尝试？'
    return window.confirm(message)
  } catch {
    return true
  }
}

onMounted(async () => {
  const provider = (route.query.provider as string) || undefined
  const model = (route.query.model as string) || undefined
  if (!(await confirmAnalysisQuota())) {
    loading.value = false
    router.push('/')
    return
  }
  try {
    loading.value = true
    result.value = await api.analyze(parseInt(props.matchId), provider, model)
    if (result.value) {
      activeTeam.value = result.value.radiant_win ? 'dire' : 'radiant'
    }
  } catch (e: any) {
    error.value = e.message || '分析失败'
  } finally {
    loading.value = false
  }
})

const filteredEvals = computed(() => {
  if (!result.value || !result.value.position_evals) return []
  const isRadiant = activeTeam.value === 'radiant'
  const cards = isRadiant ? result.value.radiant_players : result.value.dire_players
  if (!cards || !cards.length) return []
  const teamEvals = (result.value.position_evals || []).filter(e => e.is_radiant === isRadiant)
  return cards
    .map((card, i) => {
      const pe = teamEvals[i]
      return pe ? { ...pe, _card: card } : null
    })
    .filter(Boolean) as any
})

const filteredCards = computed(() => {
  if (!result.value) return []
  const cards = activeTeam.value === 'radiant' ? result.value.radiant_players : result.value.dire_players
  return cards || []
})

function copyShareUrl() {
  if (!result.value?.share_url) return
  navigator.clipboard.writeText(result.value.share_url)
  shareCopied.value = true
  setTimeout(() => { shareCopied.value = false }, 2000)
}

function formatDuration(sec: number) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

async function confirmSmurfQuota(): Promise<boolean> {
  try {
    const quota = await api.getQuota()
    const remaining = quota?.remaining ?? quota?.analysis_remaining ?? 0
    if (remaining <= 0) {
      window.alert('今天 3 次分析机会已用完，明天再来。')
      return false
    }
    return window.confirm(`本次小号检测会消耗 1 次机会，今天还剩 ${remaining} 次。确定继续吗？`)
  } catch {
    return true
  }
}

async function checkSmurf() {
  const now = Date.now()
  if (smurfChecking.value || smurfConfirming.value || now - smurfLastRunAt < 600) return
  const mvpAccountId = result.value?.mvp?.account_id
  if (!mvpAccountId) {
    smurfError.value = '无法获取MVP的玩家ID'
    return
  }

  smurfLastRunAt = now
  smurfConfirming.value = true
  try {
    if (!(await confirmSmurfQuota())) return
  } finally {
    smurfConfirming.value = false
  }

  const seq = ++smurfRequestSeq
  smurfChecking.value = true
  smurfError.value = ''
  smurfResult.value = null
  smurfExpanded.value = false
  beginSmurfLoading()
  try {
    const result = await api.smurfCheck(mvpAccountId)
    if (seq === smurfRequestSeq) smurfResult.value = result
  } catch (e: any) {
    if (seq === smurfRequestSeq) smurfError.value = e.message || '检测失败'
  } finally {
    if (seq === smurfRequestSeq) {
      endSmurfLoading()
      smurfChecking.value = false
    }
  }
}

function smurfScoreLabel(score: number): string {
  if (score >= 0.85) return '极高'
  if (score >= 0.70) return '很高'
  if (score >= 0.55) return '较高'
  if (score >= 0.40) return '中等'
  return '较低'
}

function smurfScoreColor(score: number): string {
  if (score >= 0.70) return 'var(--down)'
  if (score >= 0.55) return 'var(--warn)'
  if (score >= 0.40) return 'var(--accent)'
  return 'var(--up)'
}
</script>

<template>
  <div class="analysis-page">
    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>AI 正在分析比赛数据，请稍候...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state container">
      <p class="error-msg">{{ error }}</p>
      <router-link to="/" class="btn btn-primary">返回首页</router-link>
    </div>

    <!-- Result -->
    <template v-else-if="result">
      <div class="container">
        <!-- 比赛概览 -->
        <div class="match-overview">
          <div class="overview-left">
            <span class="match-id">Match #{{ result.match_id }}</span>
            <span class="match-skill">{{ result.skill_level }}</span>
            <span class="match-duration">{{ formatDuration(result.duration) }}</span>
          </div>
          <div class="overview-right">
            <button class="btn btn-sm" @click="copyShareUrl">
              {{ shareCopied ? '已复制!' : '分享链接' }}
            </button>
          </div>
        </div>

        <p v-if="result.game_summary" class="game-summary">{{ result.game_summary }}</p>

        <!-- MVP + 背锅侠 双卡 -->
        <div class="hero-cards">
          <div class="hero-card mvp-card">
            <div class="card-badge mvp-badge">🏆 MVP</div>
            <PlayerCard :player="result.mvp" />
            <p class="card-reason">{{ result.mvp.reason }}</p>

            <!-- 查小号 -->
            <div class="smurf-action">
              <button
                class="smurf-btn"
                @click="checkSmurf"
                :disabled="smurfChecking || smurfConfirming"
              >
                🔍 {{ smurfChecking || smurfConfirming ? '检测中...' : '这人是小号吗？' }}
              </button>
              <div v-if="smurfChecking" class="smurf-loading-inline" aria-live="polite">
                <span class="smurf-inline-spinner"></span>
                <span>{{ smurfLoadingText }}</span>
              </div>
              <p v-if="smurfError" class="smurf-error-inline">{{ smurfError }}</p>
            </div>

            <!-- 小号检测结果 -->
            <div v-if="smurfResult" class="smurf-inline-result">
              <div class="smurf-inline-score">
                <span class="smurf-inline-num" :style="{ color: smurfScoreColor(smurfResult.score) }">
                  {{ Math.round(smurfResult.score * 100) }}%
                </span>
                <span class="smurf-inline-label" :style="{ color: smurfScoreColor(smurfResult.score) }">
                  {{ smurfScoreLabel(smurfResult.score) }}
                </span>
              </div>
              <p class="smurf-inline-roast">{{ smurfResult.roast }}</p>
              <div v-if="smurfExpanded" class="smurf-inline-details">
                <div v-for="s in smurfResult.signals" :key="s.label" class="smurf-inline-signal">
                  <span class="sis-label">{{ s.label }}</span>
                  <span class="sis-value">{{ s.value }}</span>
                </div>
              </div>
              <button class="smurf-toggle" @click="smurfExpanded = !smurfExpanded">
                {{ smurfExpanded ? '收起 ▲' : '展开 ▼' }}
              </button>
            </div>
          </div>
          <div class="hero-card sg-card">
            <div class="card-badge sg-badge">🤡 背锅侠</div>
            <PlayerCard :player="result.scapegoat" />
            <p class="card-reason">{{ result.scapegoat.reason }}</p>
          </div>
        </div>

        <!-- 阵营切换 -->
        <div class="team-tabs">
          <button :class="['team-tab radiant', { active: activeTeam === 'radiant' }]" @click="activeTeam = 'radiant'">
            <span class="team-icon">🔴</span> 天辉 <span v-if="result.radiant_win" class="crown">👑</span>
          </button>
          <button :class="['team-tab dire', { active: activeTeam === 'dire' }]" @click="activeTeam = 'dire'">
            <span class="team-icon">🟢</span> 夜魇 <span v-if="!result.radiant_win" class="crown">👑</span>
          </button>
        </div>

        <!-- 位置评估 -->
        <div class="position-grid">
          <PositionEval
            v-for="pe in filteredEvals"
            :key="(pe as any)._card.position + '_' + activeTeam"
            :eval="pe"
            :player-card="(pe as any)._card"
          />
        </div>

        <!-- 关键时间线 -->
        <h2 class="section-title">关键事件</h2>
        <Timeline :events="result.timeline" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.analysis-page { padding: 30px 0 60px; }
.loading-state { display: flex; flex-direction: column; align-items: center; padding: 80px 20px; gap: 16px; color: var(--text-secondary); }
.spinner { width: 36px; height: 36px; border: 3px solid var(--border); border-top-color: var(--gold); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-state { text-align: center; padding: 60px 20px; }
.error-msg { color: var(--red); margin-bottom: 16px; }
.match-overview { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--r); margin-bottom: 20px; }
.overview-left { display: flex; gap: 16px; align-items: center; font-size: 13px; color: var(--text-secondary); }
.match-id { font-weight: 700; color: var(--text-primary); font-size: 14px; }
.match-skill { background: var(--accent-soft); color: var(--accent); padding: 2px 10px; border-radius: var(--r-sm); font-size: 11px; font-weight: 600; letter-spacing: 0.03em; }
.game-summary { text-align: center; font-size: 15px; color: var(--text-secondary); font-style: italic; padding: 16px 0 24px; border-bottom: 1px solid var(--border); margin-bottom: 28px; line-height: 1.6; }
.hero-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 32px; }
@media (max-width: 640px) { .hero-cards { grid-template-columns: 1fr; } }
.hero-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--r); padding: 24px; position: relative; transition: border-color var(--transition); }
.hero-card:hover { border-color: var(--border-light); }
.mvp-card { border-color: var(--accent); background: rgba(212,168,67,.04); }
.sg-card { border-color: rgba(248,81,73,.2); }
.card-badge { position: absolute; top: -12px; left: 20px; padding: 4px 14px; border-radius: var(--r-sm); font-size: 11px; font-weight: 800; letter-spacing: 0.04em; }
.mvp-badge { background: var(--accent); color: var(--on-accent); }
.sg-badge { background: #3a3a3a; color: #ccc; }
.card-reason { margin-top: 14px; font-size: 13px; color: var(--ink-2); line-height: 1.6; }

/* ── 小号检测 ── */
.smurf-action { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); }
.smurf-btn {
  background: none; border: 1px solid var(--border);
  padding: 6px 14px; border-radius: var(--r-sm);
  font-size: 12px; color: var(--ink-2); font-weight: 600;
  cursor: pointer; transition: all var(--transition);
}
.smurf-btn:hover { border-color: var(--accent); color: var(--accent); }
.smurf-loading-inline {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--ink-2);
}
.smurf-inline-spinner {
  width: 14px;
  height: 14px;
  flex: 0 0 14px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: smurf-spin 0.8s linear infinite;
}
@keyframes smurf-spin { to { transform: rotate(360deg); } }
.smurf-error-inline { font-size: 12px; color: var(--red-400); margin-top: 6px; }

.smurf-inline-result { margin-top: 10px; }
.smurf-inline-score { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.smurf-inline-num { font-size: 18px; font-weight: 800; }
.smurf-inline-label { font-size: 11px; font-weight: 700; background: rgba(255,255,255,.05); padding: 1px 8px; border-radius: var(--r-sm); }
.smurf-inline-roast { font-size: 12px; color: var(--ink-2); line-height: 1.6; font-style: italic; margin-bottom: 8px; }
.smurf-inline-details { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-bottom: 6px; }
.smurf-inline-signal { display: flex; align-items: center; gap: 4px; font-size: 11px; }
.sis-label { color: var(--ink-3); }
.sis-value { color: var(--ink-2); font-weight: 700; }
.smurf-toggle {
  background: none; border: none;
  font-size: 11px; color: var(--accent); font-weight: 600;
  cursor: pointer; padding: 0;
}
.smurf-toggle:hover { color: #c49a36; }

.team-tabs { display: flex; gap: 2px; margin-bottom: 20px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--r); padding: 4px; }
.team-tab { flex: 1; padding: 11px 16px; font-size: 14px; font-weight: 700; border: none; border-radius: var(--r-sm); background: transparent; color: var(--ink-3); cursor: pointer; transition: all var(--transition); display: flex; align-items: center; justify-content: center; gap: 6px; }
.team-tab:hover { color: var(--text-primary); background: rgba(255,255,255,0.03); }
.team-tab.radiant.active { background: rgba(63,185,80,.1); color: var(--green-400); }
.team-tab.dire.active { background: rgba(248,81,73,.1); color: var(--red-400); }
.team-icon { font-size: 16px; }
.crown { font-size: 13px; }
.section-title { font-size: 15px; font-weight: 700; margin: 32px 0 16px; padding-bottom: 0; border-bottom: none; letter-spacing: -0.01em; color: var(--ink-2); text-transform: uppercase; font-size: 11px; letter-spacing: .06em; }
.position-grid { display: flex; flex-direction: column; gap: 10px; margin-bottom: 8px; }
@media (max-width: 480px) {
  .match-overview { flex-direction: column; gap: 10px; align-items: flex-start; }
  .overview-left { flex-wrap: wrap; gap: 8px; }
  .hero-card { padding: 16px; }
  .card-badge { top: -10px; left: 12px; }
  .card-reason { font-size: 12px; }
  .team-tab { padding: 9px 10px; font-size: 12px; }
  .section-title { margin: 20px 0 12px; }
}
</style>
