<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type MatchItem, type SmurfResult } from '../api'

const router = useRouter()

// ── 比赛分析 ──
const searchMode = ref<'player' | 'match'>('player')
const playerId = ref('')
const matchId = ref('')
const loading = ref(false)
const error = ref('')
const playerName = ref('')
const matches = ref<MatchItem[]>([])
const providers = ref<{ id: string; name: string; models: string[] }[]>([])
const selectedProvider = ref('')
const selectedModel = ref('')

// ── 捕鱼执法 ──
const smurfId = ref('')
const smurfLoading = ref(false)
const smurfConfirming = ref(false)
const smurfError = ref('')
const smurfResult = ref<SmurfResult | null>(null)
const smurfExpanded = ref(false)
const smurfCacheHint = ref('')
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

onMounted(() => {
  const saved = localStorage.getItem('dota2_player_id')
  if (saved) playerId.value = saved
})

const currentModels = computed(() => {
  const p = providers.value.find(p => p.id === selectedProvider.value)
  return p?.models ?? []
})

async function loadProviders() {
  try {
    const data = await api.getProviders()
    providers.value = data.providers
    if (data.providers.length > 0) {
      const preferred = data.providers.find(p => p.id === 'deepseek') || data.providers[0]
      selectedProvider.value = preferred.id
      selectedModel.value = preferred.models[0]
    }
  } catch {}
}

loadProviders()

watch(selectedProvider, () => {
  selectedModel.value = currentModels.value[0] || ''
})

async function confirmQuota(kind: 'analysis' | 'smurf'): Promise<boolean> {
  try {
    const quota = await api.getQuota()
    const remaining = quota?.remaining ?? quota?.analysis_remaining ?? 0
    if (remaining <= 0) {
      const message = kind === 'analysis'
        ? '今天 3 次分析机会已用完，明天再来。已分析过的比赛仍可重复查看。'
        : '今天 3 次分析机会已用完，明天再来。'
      window.alert(message)
      return false
    }
    const label = kind === 'analysis' ? '比赛分析' : '小号检测'
    return window.confirm(`本次${label}会消耗 1 次机会，今天还剩 ${remaining} 次。确定继续吗？`)
  } catch {
    // 额度查询失败时不阻断，由后端接口最终兜底。
    return true
  }
}

// ── 比赛分析 methods ──
async function searchPlayer() {
  const id = parseInt(playerId.value.trim())
  if (!id) { error.value = '请输入有效的玩家ID'; return }
  loading.value = true
  error.value = ''
  localStorage.setItem('dota2_player_id', playerId.value.trim())
  try {
    const data = await api.getPlayerMatches(id)
    playerName.value = data.player_name
    matches.value = data.matches
  } catch (e: any) {
    error.value = e.message || '搜索失败'
    matches.value = []
  } finally {
    loading.value = false
  }
}

async function analyzeMatch(matchId: number) {
  router.push({
    path: `/analysis/${matchId}`,
    query: { provider: selectedProvider.value, model: selectedModel.value },
  })
}

async function goDirectMatch() {
  const id = parseInt(matchId.value.trim())
  if (!id) { error.value = '请输入有效的比赛ID'; return }
  router.push({
    path: `/analysis/${id}`,
    query: { provider: selectedProvider.value, model: selectedModel.value },
  })
}

// ── 捕鱼执法 methods ──
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
      if (cached?.score !== undefined) {
        smurfResult.value = cached
        smurfExpanded.value = false
        smurfCacheHint.value = cached.message || '已使用小号检测缓存，不消耗今日次数'
        return
      }
    } catch {}

    if (!(await confirmQuota('smurf'))) return
  } finally {
    smurfConfirming.value = false
  }

  const seq = ++smurfRequestSeq
  smurfLoading.value = true
  smurfError.value = ''
  smurfResult.value = null
  smurfExpanded.value = false
  smurfCacheHint.value = ''
  beginSmurfLoading()
  try {
    const result = await api.smurfCheck(id)
    if (seq === smurfRequestSeq) {
      smurfResult.value = result
      smurfCacheHint.value = result.cached ? (result.message || '已使用缓存，不消耗次数') : ''
    }
  } catch (e: any) {
    if (seq === smurfRequestSeq) smurfError.value = e.message || '检测失败'
  } finally {
    if (seq === smurfRequestSeq) {
      endSmurfLoading()
      smurfLoading.value = false
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

function formatDuration(sec: number) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleDateString('zh-CN')
}
</script>

<template>
  <div class="home">
    <section class="hero">
      <div class="container">
        <h1 class="hero-title">🏆 比赛结束了，锅得分好</h1>
        <p class="hero-sub">输入比赛ID或玩家ID，AI帮你评选MVP、找出背锅侠、逐位置给出改进建议</p>

        <!-- 双卡片布局 -->
        <div class="dual-cards">
          <!-- 左：比赛分析 -->
          <div class="feature-card">
            <div class="card-header">
              <span class="card-icon">📊</span>
              <span class="card-title">比赛分析</span>
            </div>

            <div class="provider-bar" v-if="providers.length > 0">
              <span class="provider-label">AI模型:</span>
              <select v-model="selectedProvider" class="select-sm">
                <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
              <select v-model="selectedModel" class="select-sm" v-if="currentModels.length > 1">
                <option v-for="m in currentModels" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>

            <div class="mode-tabs">
              <button
                :class="['mode-tab', { active: searchMode === 'player' }]"
                @click="searchMode = 'player'"
              >搜玩家</button>
              <button
                :class="['mode-tab', { active: searchMode === 'match' }]"
                @click="searchMode = 'match'"
              >比赛ID</button>
            </div>

            <div v-if="searchMode === 'player'" class="card-search">
              <input
                v-model="playerId"
                type="text"
                placeholder="输入玩家ID（Steam32 ID）"
                class="search-input card-input"
                @keyup.enter="searchPlayer"
              />
              <button class="btn btn-primary" @click="searchPlayer" :disabled="loading">
                {{ loading ? '搜索中...' : '搜索' }}
              </button>
            </div>

            <div v-else class="card-search">
              <input
                v-model="matchId"
                type="text"
                placeholder="输入比赛ID"
                class="search-input card-input"
                @keyup.enter="goDirectMatch"
              />
              <button class="btn btn-primary" @click="goDirectMatch">开始分析</button>
            </div>
          </div>

          <!-- 右：捕鱼执法 -->
          <div class="feature-card">
            <div class="card-header">
              <span class="card-icon">🎣</span>
              <span class="card-title">捕鱼执法</span>
            </div>
            <p class="card-desc">输入玩家ID，检测是否为小号炸鱼</p>

            <div class="card-search">
              <input
                v-model="smurfId"
                type="text"
                placeholder="输入玩家ID（Steam32 ID）"
                class="search-input card-input"
                @keyup.enter="runSmurfCheck"
              />
              <button class="btn btn-primary" @click="runSmurfCheck" :disabled="smurfLoading || smurfConfirming">
                {{ smurfLoading || smurfConfirming ? '检测中...' : '检测' }}
              </button>
            </div>

            <p v-if="smurfError" class="error-msg">{{ smurfError }}</p>

            <div v-if="smurfLoading" class="smurf-loading" aria-live="polite">
              <span class="smurf-spinner"></span>
              <div class="smurf-loading-copy">
                <strong>捕鱼执法中</strong>
                <span>{{ smurfLoadingText }}</span>
                <small>首次查询较慢，稍后会快很多</small>
              </div>
              <div class="smurf-loading-bar">
                <span></span>
              </div>
            </div>

            <!-- 检测结果 -->
            <div v-if="smurfResult" class="smurf-result" :class="{ expanded: smurfExpanded }">
              <div class="smurf-score-row">
                <div class="smurf-score-bar-bg">
                  <div
                    class="smurf-score-bar-fill"
                    :style="{
                      width: Math.round(smurfResult.score * 100) + '%',
                      background: smurfScoreColor(smurfResult.score),
                    }"
                  ></div>
                </div>
                <span class="smurf-score-num" :style="{ color: smurfScoreColor(smurfResult.score) }">
                  {{ Math.round(smurfResult.score * 100) }}%
                </span>
                <span class="smurf-score-label" :style="{ color: smurfScoreColor(smurfResult.score) }">
                  {{ smurfScoreLabel(smurfResult.score) }}
                </span>
              </div>

              <p class="smurf-roast">{{ smurfResult.roast }}</p>
              <p v-if="smurfCacheHint" class="smurf-cache-hint">{{ smurfCacheHint }}</p>

              <div v-if="smurfExpanded" class="smurf-details">
                <div
                  v-for="s in smurfResult.signals"
                  :key="s.label"
                  class="smurf-signal"
                >
                  <div class="signal-header">
                    <span class="signal-label">{{ s.label }}</span>
                    <span class="signal-value">{{ s.value }}</span>
                  </div>
                  <div class="signal-bar-bg">
                    <div
                      class="signal-bar-fill"
                      :style="{ width: Math.round(s.score * 100) + '%' }"
                    ></div>
                  </div>
                  <span class="signal-detail">{{ s.detail }}</span>
                </div>
              </div>

              <button class="smurf-toggle" @click="smurfExpanded = !smurfExpanded">
                {{ smurfExpanded ? '收起证据 ▲' : '展开证据 ▼' }}
              </button>
            </div>
          </div>
        </div>

        <p v-if="error" class="error-msg">{{ error }}</p>
      </div>
    </section>

    <!-- 比赛列表 -->
    <section v-if="matches.length > 0" class="matches-section">
      <div class="container">
        <h2 class="section-title">{{ playerName }} 的最近比赛</h2>
        <div class="match-grid">
          <div
            v-for="m in matches"
            :key="m.match_id"
            class="match-card"
            @click="analyzeMatch(m.match_id)"
          >
            <img :src="m.hero_icon" :alt="m.hero_name" class="hero-img" loading="lazy" />
            <div class="match-info">
              <div class="match-hero">{{ m.hero_name }}</div>
              <div class="match-kda">{{ m.kills }}/{{ m.deaths }}/{{ m.assists }}</div>
              <div class="match-meta">
                <span :class="['tag', m.is_win ? 'tag-win' : 'tag-loss']">
                  {{ m.is_win ? 'WIN' : 'LOSS' }}
                </span>
                <span class="match-time">{{ formatDuration(m.duration) }}</span>
                <span class="match-date">{{ formatTime(m.start_time) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  padding: 64px 0 48px;
  text-align: center;
}
.hero-title {
  font-size: 34px; font-weight: 800; margin-bottom: 10px;
  color: var(--ink-1); letter-spacing: -0.02em;
}
.hero-sub {
  color: var(--text-secondary); margin-bottom: 36px; font-size: 15px;
  font-weight: 500; line-height: 1.6;
}

/* ── 双卡片 ── */
.dual-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  max-width: 820px;
  margin: 0 auto;
}
@media (max-width: 700px) {
  .dual-cards { grid-template-columns: 1fr; max-width: 420px; }
}

.feature-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 24px 22px 22px;
  text-align: center;
  transition: border-color var(--transition);
}
.feature-card:hover { border-color: var(--border-light); }

.card-header {
  display: flex; align-items: center; justify-content: center;
  gap: 8px; margin-bottom: 16px;
}
.card-icon { font-size: 20px; }
.card-title {
  font-size: 16px; font-weight: 800;
  color: var(--ink-1); letter-spacing: -0.01em;
}
.card-desc {
  font-size: 13px; color: var(--ink-3);
  margin-bottom: 16px; font-weight: 500;
}

/* ── 模型选择（仅左卡片） ── */
.provider-bar {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  margin-bottom: 16px; font-size: 12px; color: var(--text-secondary); font-weight: 500;
}

/* ── 模式标签 ── */
.mode-tabs {
  display: inline-flex; background: var(--panel-2);
  border-radius: var(--r-sm);
  overflow: hidden; margin-bottom: 16px;
}
.mode-tab {
  padding: 7px 16px; font-size: 12px; font-weight: 600;
  border: none; background: transparent; color: var(--text-secondary);
  transition: all var(--transition);
}
.mode-tab.active {
  background: var(--accent); color: var(--on-accent);
}

/* ── 搜索行 ── */
.card-search {
  display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;
}
.card-input {
  width: 200px; max-width: 60%;
}

/* ── 捕鱼 loading ── */
.smurf-loading {
  margin-top: 16px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  background: var(--panel-2);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
}
.smurf-spinner {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: smurf-spin 0.8s linear infinite;
}
@keyframes smurf-spin { to { transform: rotate(360deg); } }
.smurf-loading-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: var(--ink-2);
  font-size: 12px;
}
.smurf-loading-copy strong {
  color: var(--ink-1);
  font-size: 13px;
}
.smurf-loading-copy small {
  color: var(--ink-3);
  font-size: 10px;
}
.smurf-loading-bar {
  width: 76px;
  height: 4px;
  overflow: hidden;
  border-radius: 2px;
  background: var(--panel-1);
}
.smurf-loading-bar span {
  display: block;
  width: 42%;
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  animation: smurf-loading-slide 1.2s ease-in-out infinite;
}
@keyframes smurf-loading-slide {
  0% { transform: translateX(-110%); }
  50% { transform: translateX(80%); }
  100% { transform: translateX(220%); }
}

/* ── 捕鱼结果 ── */
.smurf-result {
  margin-top: 16px; text-align: left;
}
.smurf-score-row {
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.smurf-score-bar-bg {
  flex: 1; height: 8px; background: var(--panel-2);
  border-radius: 4px; overflow: hidden;
}
.smurf-score-bar-fill {
  height: 100%; border-radius: 4px; transition: width 0.6s ease;
}
.smurf-score-num {
  font-size: 20px; font-weight: 800; min-width: 44px; text-align: right;
}
.smurf-score-label {
  font-size: 12px; font-weight: 700;
  background: rgba(255,255,255,.05); padding: 2px 8px;
  border-radius: var(--r-sm);
}

.smurf-roast {
  font-size: 13px; color: var(--ink-2); line-height: 1.6;
  font-style: italic; margin-bottom: 10px;
}
.smurf-cache-hint {
  font-size: 11px; color: var(--accent); margin: -2px 0 10px;
}

.smurf-details { margin-top: 10px; }
.smurf-signal {
  margin-bottom: 8px;
}
.signal-header {
  display: flex; justify-content: space-between;
  font-size: 12px; margin-bottom: 3px;
}
.signal-label { color: var(--ink-3); font-weight: 500; }
.signal-value { color: var(--ink-2); font-weight: 600; }
.signal-bar-bg {
  height: 4px; background: var(--panel-2);
  border-radius: 2px; overflow: hidden; margin-bottom: 2px;
}
.signal-bar-fill {
  height: 100%; background: var(--accent);
  border-radius: 2px; transition: width 0.5s ease;
}
.signal-detail {
  font-size: 10px; color: var(--ink-3);
}

.smurf-toggle {
  display: block; margin-top: 12px; padding: 0;
  background: none; border: none;
  font-size: 12px; color: var(--accent); font-weight: 600;
  cursor: pointer;
}
.smurf-toggle:hover { color: #c49a36; }

/* ── 通用 ── */
.error-msg { color: var(--red-400); margin-top: 12px; font-size: 13px; font-weight: 500; }
.matches-section { padding: 24px 0 80px; }
.section-title { font-size: 18px; font-weight: 700; margin-bottom: 20px; letter-spacing: -0.01em; }
.match-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;
}
.match-card {
  display: flex; align-items: center; gap: 14px; padding: 14px 16px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--r); cursor: pointer;
  transition: all var(--transition);
}
.match-card:hover {
  border-color: var(--border-light); background: var(--panel-2);
  box-shadow: var(--shadow); transform: translateY(-1px);
}
.hero-img { width: 60px; height: 34px; border-radius: var(--r-sm); object-fit: cover; }
.match-info { flex: 1; min-width: 0; }
.match-hero {
  font-weight: 600; font-size: 14px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; letter-spacing: -0.01em;
}
.match-kda { font-size: 13px; color: var(--ink-2); margin: 3px 0; font-weight: 500; }
.match-meta {
  display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--ink-3); font-weight: 500;
}
</style>
