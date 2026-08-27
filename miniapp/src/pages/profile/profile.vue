<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '../../api/index.js'
import StepChart from '../../components/StepChart.vue'

const loading = ref(true)
const profile = ref(null) // 绑定后的档案
const steamInput = ref('')
const binding = ref(false)
const refreshing = ref(false)
const error = ref('')

// 历史段位 (梯状图)
const historyRank = ref([])
const historyLoading = ref(false)
const chartWidth = ref(320)
const chartHeight = ref(220)

const bound = computed(() => !!(profile.value && profile.value.bound))

const internalRec = computed(() => profile.value?.internal_record || {})
const internalWinText = computed(() => {
  const r = internalRec.value
  if (r.win_rate === null || r.win_rate === undefined) return '—'
  return `${r.win_rate}%`
})
const internalTotal = computed(() => internalRec.value?.total || 0)
const internalWinClass = computed(() => {
  const r = internalRec.value
  if (!r || r.win_rate === null || r.win_rate === undefined) return ''
  return r.win_rate >= 50 ? 'win' : (r.win_rate < 50 ? 'lose' : '')
})

onLoad(() => {
  // 适配屏幕宽度: 屏宽 - 左右 padding(24rpx*2) - 卡片内边距(28rpx*2)
  try {
    const info = uni.getSystemInfoSync()
    const rpxRatio = info.windowWidth / 750
    const outerPad = 24 * 2 * rpxRatio
    const cardPad = 28 * 2 * rpxRatio
    chartWidth.value = Math.max(260, Math.floor(info.windowWidth - outerPad - cardPad))
    chartHeight.value = Math.max(180, Math.floor(chartWidth.value * 0.62))
  } catch (e) {}
  loadProfile()
})

async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.getMyProfile()
    profile.value = res
    if (res && res.bound) loadHistoryRank()
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadHistoryRank() {
  if (historyLoading.value) return
  historyLoading.value = true
  try {
    const res = await api.getHistoryRank()
    historyRank.value = res?.data || []
  } catch (e) {
    historyRank.value = []
  } finally {
    historyLoading.value = false
  }
}

async function bind() {
  const input = (steamInput.value || '').trim()
  if (!input) {
    uni.showToast({ title: '请输入 Steam ID 或主页链接', icon: 'none' })
    return
  }
  if (binding.value) return
  binding.value = true
  uni.showLoading({ title: '正在验证账号...', mask: true })
  try {
    const res = await api.bindSteam(input)
    profile.value = res
    steamInput.value = ''
    uni.showToast({ title: '绑定成功', icon: 'success' })
    loadHistoryRank()
  } catch (e) {
    let msg = e.message || '绑定失败'
    try { msg = JSON.parse(msg).detail || msg } catch (err) {}
    uni.showToast({ title: msg, icon: 'none', duration: 2500 })
  } finally {
    uni.hideLoading()
    binding.value = false
  }
}

async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    // 后端超过 24h 才会真正重拉，这里通过重新绑定同账号强制刷新
    const res = await api.bindSteam(profile.value.steam_id64)
    profile.value = res
    uni.showToast({ title: '已刷新', icon: 'success' })
    // 重新拉历史段位 (绑定接口不返回此数据)
    loadHistoryRank()
  } catch (e) {
    let msg = e.message || '刷新失败'
    try { msg = JSON.parse(msg).detail || msg } catch (err) {}
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    refreshing.value = false
  }
}

function confirmUnbind() {
  uni.showModal({
    title: '解绑 Steam',
    content: '解绑后将无法发起或参与约战，确定解绑吗？',
    confirmText: '解绑',
    confirmColor: '#f85149',
    success: async (res) => {
      if (!res.confirm) return
      try {
        profile.value = await api.unbindSteam()
      } catch (e) {
        uni.showToast({ title: e.message || '解绑失败', icon: 'none' })
      }
    },
  })
}

function valOrDash(v, suffix) {
  if (v === null || v === undefined || v === '') return '未知'
  return suffix ? `${v}${suffix}` : String(v)
}
</script>

<template>
  <view class="profile-page">
    <!-- 加载中 -->
    <view v-if="loading" class="loading-state">
      <view class="spinner"></view>
      <text class="loading-text">加载中...</text>
    </view>

    <template v-else-if="bound">
      <!-- 已绑定: 档案头 -->
      <view class="profile-card">
        <view class="profile-head">
          <image class="avatar" :src="profile.avatar" mode="aspectFill" />
          <view class="head-info">
            <text class="steam-name">{{ profile.steam_name }}</text>
            <text class="account-id">ID: {{ profile.account_id }}</text>
            <view class="rank-badge" v-if="profile.rank_name">
              <text class="rank-text">{{ profile.rank_name }}</text>
            </view>
            <view class="rank-badge rank-unknown" v-else>
              <text class="rank-text">段位未知</text>
            </view>
          </view>
        </view>
        <text class="unknown-tip" v-if="!profile.rank_name">
          段位需要玩家在 OpenDota 授权登录过才能读取
        </text>
      </view>

      <!-- 数据统计 -->
      <view class="stats-grid">
        <view class="stat-cell">
          <text class="stat-val" :class="{ win: profile.win_rate >= 50 }">{{ valOrDash(profile.win_rate, '%') }}</text>
          <text class="stat-lbl">近100场胜率</text>
        </view>
        <view class="stat-cell">
          <text class="stat-val" :class="internalWinClass">{{ internalWinText }}</text>
          <text class="stat-lbl">内战胜率 · {{ internalTotal }}场</text>
        </view>
        <view class="stat-cell">
          <text class="stat-val">{{ valOrDash(profile.total_games) }}</text>
          <text class="stat-lbl">总场次</text>
        </view>
        <view class="stat-cell">
          <text class="stat-val">{{ valOrDash(profile.main_position_label) }}</text>
          <text class="stat-lbl">常玩位置</text>
        </view>
      </view>

      <!-- 历史段位 -->
      <view class="card history-card">
        <view class="section-head">
          <text class="section-title">历史段位</text>
          <text class="section-sub" v-if="historyRank.length">段位走势 · {{ historyRank.length }} 条记录</text>
          <text class="section-sub" v-else-if="!historyLoading">暂无数据</text>
        </view>
        <view v-if="historyLoading" class="hist-loading">
          <view class="spinner-sm"></view>
          <text class="hist-loading-text">拉取历史段位中...</text>
        </view>
        <StepChart
          v-else
          :data="historyRank"
          :width="chartWidth"
          :height="chartHeight"
        />
      </view>

      <!-- 操作 -->
      <view class="actions">
        <view class="action-btn primary" @click="refresh">
          <text class="action-text primary-text">{{ refreshing ? '刷新中...' : '刷新数据' }}</text>
        </view>
        <view class="action-btn danger" @click="confirmUnbind">
          <text class="action-text danger-text">解绑 Steam</text>
        </view>
      </view>
    </template>

    <!-- 未绑定 -->
    <view v-else class="unbound">
      <view class="avatar-placeholder">
        <text class="avatar-q">?</text>
      </view>
      <text class="unbound-title">绑定 Steam 账号</text>
      <text class="unbound-sub">绑定后展示段位 / 胜率 / 常玩位置</text>
      <text class="unbound-sub">并可发起或参与约战</text>

      <view class="bind-form">
        <input
          class="bind-input"
          v-model="steamInput"
          placeholder="SteamID64 / 自定义URL ID / 主页链接"
          placeholder-class="input-ph"
          :disabled="binding"
        />
        <view class="bind-btn" :class="{ disabled: binding }" @click="bind">
          <text class="bind-text">{{ binding ? '绑定中...' : '绑定' }}</text>
        </view>
      </view>
      <text class="bind-tip">推荐用游戏内数字 ID（个人资料页那个短号），</text>
      <text class="bind-tip">也支持 SteamID64、自定义 URL ID、主页链接</text>
    </view>
  </view>
</template>

<style scoped>
.profile-page {
  min-height: 100vh;
  padding: 32rpx 24rpx 40rpx;
  box-sizing: border-box;
}
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20rpx;
  padding: 200rpx 0;
}
.spinner {
  width: 52rpx;
  height: 52rpx;
  border: 4rpx solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { font-size: 26rpx; color: var(--ink-3); }

/* ── 已绑定 ── */
.profile-card {
  background: var(--bg);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 36rpx 28rpx;
  margin-bottom: 24rpx;
}
.profile-head { display: flex; gap: 24rpx; align-items: center; }
.avatar {
  width: 140rpx;
  height: 140rpx;
  border-radius: var(--r-sm);
  border: 1rpx solid var(--border-light);
  flex-shrink: 0;
}
.head-info { display: flex; flex-direction: column; gap: 8rpx; min-width: 0; }
.steam-name {
  font-size: 34rpx;
  font-weight: 800;
  color: var(--ink-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.account-id { font-size: 22rpx; color: var(--ink-3); }
.rank-badge {
  align-self: flex-start;
  margin-top: 6rpx;
  background: var(--accent-soft);
  padding: 4rpx 18rpx;
  border-radius: var(--r-sm);
}
.rank-text { font-size: 24rpx; font-weight: 700; color: var(--accent); }
.rank-unknown { background: rgba(156, 147, 132, .1); }
.rank-unknown .rank-text { color: var(--ink-3); }
.unknown-tip {
  display: block;
  margin-top: 20rpx;
  font-size: 22rpx;
  color: var(--ink-3);
  line-height: 1.5;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
  margin-bottom: 24rpx;
}
.stat-cell {
  background: var(--bg);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 24rpx 20rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}
.stat-cell.full-row { grid-column: 1 / -1; }

/* ── 历史段位卡片 ── */
.history-card {
  margin-bottom: 24rpx;
  padding: 24rpx 20rpx 18rpx;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 14rpx;
}
.section-title {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--ink-1);
}
.section-sub {
  font-size: 21rpx;
  color: var(--ink-3);
}
.hist-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 40rpx 0;
}
.spinner-sm {
  width: 36rpx;
  height: 36rpx;
  border: 3rpx solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin-sm .8s linear infinite;
}
@keyframes spin-sm { to { transform: rotate(360deg); } }
.hist-loading-text {
  font-size: 22rpx;
  color: var(--ink-3);
}
.hist-tip {
  display: block;
  margin-top: 10rpx;
  font-size: 20rpx;
  color: var(--ink-3);
  text-align: center;
  line-height: 1.5;
}
.stat-val {
  font-size: 38rpx;
  font-weight: 800;
  color: var(--ink-1);
  letter-spacing: -0.5rpx;
}
.stat-val.win { color: var(--up); }
.stat-val.lose { color: var(--down); }
.stat-lbl { font-size: 22rpx; color: var(--ink-3); }

.actions { display: flex; gap: 16rpx; }
.action-btn {
  flex: 1;
  padding: 22rpx 0;
  border-radius: var(--r);
  text-align: center;
  background: var(--panel-2);
  border: 1rpx solid var(--border);
}
.action-btn:active { opacity: .8; }
.action-btn.primary { background: var(--accent-soft); border-color: rgba(212, 168, 67, .3); }
.action-btn.danger { background: rgba(248, 81, 73, .06); border-color: rgba(248, 81, 73, .2); }
.action-text { font-size: 27rpx; font-weight: 700; }
.primary-text { color: var(--accent); }
.danger-text { color: var(--down); }

/* ── 未绑定 ── */
.unbound {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 100rpx 40rpx 40rpx;
}
.avatar-placeholder {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  background: var(--panel-2);
  border: 2rpx dashed var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20rpx;
}
.avatar-q { font-size: 64rpx; color: var(--ink-3); font-weight: 700; }
.unbound-title { font-size: 34rpx; font-weight: 800; color: var(--ink-1); }
.unbound-sub { font-size: 24rpx; color: var(--ink-3); }

.bind-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-top: 48rpx;
}
.bind-input {
  background: var(--bg);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 0 24rpx;
  height: 84rpx;
  line-height: 84rpx;
  font-size: 26rpx;
  color: var(--ink-1);
  width: 100%;
  box-sizing: border-box;
}
.input-ph { color: var(--ink-3); }
.bind-btn {
  padding: 22rpx 0;
  background: var(--accent);
  border-radius: var(--r);
  text-align: center;
}
.bind-btn.disabled { opacity: .6; }
.bind-btn:active { opacity: .85; }
.bind-text { font-size: 27rpx; font-weight: 700; color: var(--on-accent); }
.bind-tip {
  font-size: 21rpx;
  color: var(--ink-3);
  line-height: 1.6;
  margin-top: 8rpx;
}
</style>
