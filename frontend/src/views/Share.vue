<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api, type AnalysisResult } from '../api'
import PlayerCard from '../components/PlayerCard.vue'
import PositionEval from '../components/PositionEval.vue'
import Timeline from '../components/Timeline.vue'

const props = defineProps<{ shareId: string }>()

const result = ref<AnalysisResult | null>(null)
const loading = ref(true)
const error = ref('')
const activeTeam = ref<'radiant' | 'dire'>('radiant')

onMounted(async () => {
  try {
    result.value = await api.getSharedAnalysis(props.shareId)
    if (result.value) {
      activeTeam.value = result.value.radiant_win ? 'dire' : 'radiant'
    }
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
})

const filteredEvals = computed(() => {
  if (!result.value || !result.value.position_evals) return []
  const isRadiant = activeTeam.value === 'radiant'
  const cards = isRadiant ? result.value.radiant_players : result.value.dire_players
  if (!cards || !cards.length) return []
  const evals = result.value.position_evals || []
  const teamEvals = evals.filter(e => e.is_radiant === isRadiant)
  const pool = teamEvals.length ? teamEvals : evals
  // 按 account_id/位置/名字精确匹配点评，避免英雄数据和评论错位
  const used = new Set<any>()
  return cards
    .map(card => {
      const pe =
        pool.find(e => e.account_id != null && e.account_id === card.account_id && !used.has(e)) ||
        pool.find(e => e.position === card.position && !used.has(e)) ||
        pool.find(e => e.player_name === card.player_name && !used.has(e))
      if (!pe || used.has(pe)) return null
      used.add(pe)
      return { ...pe, _card: card }
    })
    .filter(Boolean) as any
})

const filteredCards = computed(() => {
  if (!result.value) return []
  const cards = activeTeam.value === 'radiant' ? result.value.radiant_players : result.value.dire_players
  return cards || []
})

function formatDuration(sec: number) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="analysis-page">
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载分享内容...</p>
    </div>

    <div v-else-if="error" class="error-state container">
      <p class="error-msg">{{ error }}</p>
      <router-link to="/" class="btn btn-primary">返回首页</router-link>
    </div>

    <template v-else-if="result">
      <div class="container">
        <div class="match-overview">
          <div class="overview-left">
            <span class="match-id">Match #{{ result.match_id }}</span>
            <span class="match-skill">{{ result.skill_level }}</span>
            <span class="match-duration">{{ formatDuration(result.duration) }}</span>
          </div>
          <div class="overview-right">
            <span class="shared-badge">分享的分析</span>
          </div>
        </div>

        <p v-if="result.game_summary" class="game-summary">{{ result.game_summary }}</p>

        <div class="hero-cards">
          <div class="hero-card mvp-card">
            <div class="card-badge mvp-badge">🏆 MVP</div>
            <PlayerCard :player="result.mvp" />
            <p class="card-reason">{{ result.mvp.reason }}</p>
          </div>
          <div class="hero-card sg-card">
            <div class="card-badge sg-badge">🤡 背锅侠</div>
            <PlayerCard :player="result.scapegoat" />
            <p class="card-reason">{{ result.scapegoat.reason }}</p>
          </div>
        </div>

        <div class="team-tabs">
          <button :class="['team-tab radiant', { active: activeTeam === 'radiant' }]" @click="activeTeam = 'radiant'">
            <span class="team-icon">🔴</span> 天辉 <span v-if="result.radiant_win" class="crown">👑</span>
          </button>
          <button :class="['team-tab dire', { active: activeTeam === 'dire' }]" @click="activeTeam = 'dire'">
            <span class="team-icon">🟢</span> 夜魇 <span v-if="!result.radiant_win" class="crown">👑</span>
          </button>
        </div>

        <div class="position-grid">
          <PositionEval
            v-for="pe in filteredEvals"
            :key="(pe as any)._card.position + '_' + activeTeam"
            :eval="pe"
            :player-card="(pe as any)._card"
          />
        </div>

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
