<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type MatchItem } from '../api'

const router = useRouter()

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

function goDirectMatch() {
  const id = parseInt(matchId.value.trim())
  if (!id) { error.value = '请输入有效的比赛ID'; return }
  router.push({
    path: `/analysis/${id}`,
    query: { provider: selectedProvider.value, model: selectedModel.value },
  })
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

        <!-- AI 模型选择 -->
        <div class="provider-bar" v-if="providers.length > 0">
          <span class="provider-label">AI模型:</span>
          <select v-model="selectedProvider" class="select-sm">
            <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <select v-model="selectedModel" class="select-sm" v-if="currentModels.length > 1">
            <option v-for="m in currentModels" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>

        <!-- 搜索模式切换 -->
        <div class="mode-tabs">
          <button
            :class="['mode-tab', { active: searchMode === 'player' }]"
            @click="searchMode = 'player'"
          >搜玩家找比赛</button>
          <button
            :class="['mode-tab', { active: searchMode === 'match' }]"
            @click="searchMode = 'match'"
          >直接输入比赛ID</button>
        </div>

        <!-- 玩家搜索 -->
        <div v-if="searchMode === 'player'" class="search-bar">
          <input
            v-model="playerId"
            type="text"
            placeholder="输入 Dota 2 玩家ID（Steam32 ID）"
            class="search-input"
            @keyup.enter="searchPlayer"
          />
          <button class="btn btn-primary" @click="searchPlayer" :disabled="loading">
            {{ loading ? '搜索中...' : '搜索比赛' }}
          </button>
        </div>

        <!-- 比赛ID直接输入 -->
        <div v-else class="search-bar">
          <input
            v-model="matchId"
            type="text"
            placeholder="输入比赛ID（例如 OpenDota 链接或纯数字）"
            class="search-input"
            @keyup.enter="goDirectMatch"
          />
          <button class="btn btn-primary" @click="goDirectMatch">开始分析</button>
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
  padding: 72px 0 48px;
  text-align: center;
}
.hero-title {
  font-size: 34px; font-weight: 800; margin-bottom: 12px;
  color: var(--ink-1); letter-spacing: -0.02em;
}
.hero-sub {
  color: var(--text-secondary); margin-bottom: 28px; font-size: 15px; font-weight: 500; line-height: 1.6;
}
.provider-bar {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  margin-bottom: 24px; font-size: 13px; color: var(--text-secondary); font-weight: 500;
}
.mode-tabs {
  display: inline-flex; background: var(--bg-card);
  border: 1px solid var(--border); border-radius: var(--r);
  overflow: hidden; margin-bottom: 20px;
}
.mode-tab {
  padding: 9px 22px; font-size: 13px; font-weight: 600;
  border: none; background: transparent; color: var(--text-secondary);
  transition: all var(--transition);
}
.mode-tab.active {
  background: var(--accent); color: var(--on-accent);
}
.search-bar { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
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
