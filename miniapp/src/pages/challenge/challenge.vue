<script setup>
import { ref } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { api, extractErr } from '../../api/index.js'

const activeTab = ref('list')
const loading = ref(false)
const listData = ref([])
const mineData = ref([])
const bound = ref(null) // null=未知 false=未绑定 true=已绑定

// ── 创建弹窗 ──
const showCreate = ref(false)
const creating = ref(false)
const form = ref({
  name: '', description: '', date: '', time: '20:00',
  rankTierMin: 0, rankTierMax: 0, mode: 'free',
  teamA: '', teamB: '', maxPlayers: 10, selfJoin: true,
})
const playerOptions = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
// 段位档位: 0=不限, 1=先锋 ... 8=不朽
const rankOptions = ['不限', '先锋', '卫士', '中军', '统帅', '传奇', '万古流芳', '超凡入圣', '不朽']

onShow(() => {
  load()
  api.getMyProfile().then((p) => { bound.value = !!p.bound }).catch(() => {})
})

onPullDownRefresh(async () => {
  await load()
  uni.stopPullDownRefresh()
})

async function load() {
  loading.value = true
  try {
    const [l, m] = await Promise.all([api.listChallenges(), api.myChallenges()])
    listData.value = l.challenges || []
    mineData.value = m.challenges || []
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  if (bound.value === false) {
    uni.showModal({
      title: '需要绑定 Steam',
      content: '发起约战前请先在「我的」页面绑定 Steam 账号',
      confirmText: '去绑定',
      success: (r) => {
        if (r.confirm) uni.switchTab({ url: '/pages/profile/profile' })
      },
    })
    return
  }
  const now = new Date(Date.now() + 86400000)
  form.value = {
    name: '', description: '',
    date: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`,
    time: '20:00',
    rankTierMin: 0, rankTierMax: 0, mode: 'free',
    teamA: '', teamB: '', maxPlayers: 10, selfJoin: true,
  }
  showCreate.value = true
}

function onDate(e) { form.value.date = e.detail.value }
function onTime(e) { form.value.time = e.detail.value }
const MODE_KEYS = ['free', 'fixed']
function onMode(e) { form.value.mode = MODE_KEYS[Number(e.detail.value)] || 'free' }
function onPlayers(e) { form.value.maxPlayers = playerOptions[Number(e.detail.value)] }
function onRankMin(e) { form.value.rankTierMin = Number(e.detail.value) }
function onRankMax(e) { form.value.rankTierMax = Number(e.detail.value) }
function onSelfJoin(e) { form.value.selfJoin = e.detail.value }

async function submitCreate() {
  const f = form.value
  if (!f.name.trim()) return uni.showToast({ title: '请填写活动名称', icon: 'none' })
  if (!f.date) return uni.showToast({ title: '请选择日期', icon: 'none' })
  if (f.mode === 'fixed') {
    if (!f.teamA.trim() || !f.teamB.trim()) return uni.showToast({ title: '请填写两个队伍名称', icon: 'none' })
    if (f.teamA.trim() === f.teamB.trim()) return uni.showToast({ title: '队伍名称不能相同', icon: 'none' })
  }
  // 0=不限; 1-8 = 段位档位
  const rankMin = f.rankTierMin > 0 ? f.rankTierMin : null
  const rankMax = f.rankTierMax > 0 ? f.rankTierMax : null
  if (rankMin !== null && rankMax !== null && rankMin > rankMax) {
    return uni.showToast({ title: '最低段位不能高于最高段位', icon: 'none' })
  }
  if (creating.value) return
  creating.value = true
  try {
    await api.createChallenge({
      name: f.name.trim(),
      description: f.description.trim(),
      activity_time: `${f.date} ${f.time}`,
      rank_tier_min: rankMin, rank_tier_max: rankMax,
      max_players: f.maxPlayers,
      mode: f.mode,
      team_a_name: f.teamA.trim(), team_b_name: f.teamB.trim(),
      self_join: f.selfJoin,
    })
    showCreate.value = false
    uni.showToast({ title: '创建成功', icon: 'success' })
    load()
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none', duration: 2500 })
  } finally {
    creating.value = false
  }
}

function openDetail(c) {
  uni.navigateTo({ url: `/pages/challenge/detail?id=${c.id}` })
}

function rankText(c) {
  const min = c.rank_tier_min
  const max = c.rank_tier_max
  if (min === null || min === undefined) return '不限'
  const minName = rankOptions[Math.floor(min / 10)] || `档位${min}`
  if (max === null || max === undefined) return `${minName}起`
  const maxName = rankOptions[Math.floor(max / 10)] || `档位${max}`
  if (Math.floor(min / 10) === Math.floor(max / 10)) return minName
  return `${minName} ~ ${maxName}`
}

function statusClass(s) {
  return {
    open: 'st-open', full: 'st-full', ended: 'st-ended', cancelled: 'st-cancelled',
  }[s] || 'st-ended'
}
</script>

<template>
  <view class="challenge-page">
    <!-- 顶部切换 -->
    <view class="seg-tabs">
      <view :class="['seg-tab', { active: activeTab === 'list' }]" @click="activeTab = 'list'">约战列表</view>
      <view :class="['seg-tab', { active: activeTab === 'mine' }]" @click="activeTab = 'mine'">我参与的</view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading && !listData.length && !mineData.length" class="loading-state">
      <view class="spinner"></view>
    </view>

    <!-- 约战列表 -->
    <view v-else-if="activeTab === 'list'" class="list-area">
      <view v-if="!listData.length" class="empty">
        <text class="empty-icon">⚔️</text>
        <text class="empty-title">还没有约战</text>
        <text class="empty-sub">点右下角 + 发起第一场对决</text>
      </view>
      <view v-for="c in listData" :key="c.id" class="card" @click="openDetail(c)">
        <view class="card-top">
          <text class="c-name">{{ c.name }}</text>
          <text :class="['st-badge', statusClass(c.status)]">{{ c.status_label }}</text>
        </view>
        <view class="c-desc" v-if="c.description">{{ c.description }}</view>
        <view class="c-meta">
          <text class="meta-item">🕒 {{ c.activity_time }}</text>
          <text class="meta-item">{{ c.mode === 'fixed' ? '🎯 固定队伍' : '🎲 自由组队' }}</text>
        </view>
        <view class="c-meta">
          <text class="meta-item">👤 {{ c.participant_count }}/{{ c.max_players }} 人</text>
          <text class="meta-item">📊 {{ rankText(c) }}</text>
          <text class="meta-item creator" v-if="c.joined">已报名</text>
        </view>
      </view>
    </view>

    <!-- 我参与的 -->
    <view v-else class="list-area">
      <view v-if="!mineData.length" class="empty">
        <text class="empty-icon">🎮</text>
        <text class="empty-title">你还没有参与任何约战</text>
        <text class="empty-sub">去约战列表找一场加入吧</text>
      </view>
      <view v-for="c in mineData" :key="c.id" class="card" @click="openDetail(c)">
        <view class="card-top">
          <view class="name-wrap">
            <text class="c-name">{{ c.name }}</text>
            <text v-if="c.is_creator" class="creator-badge">发起人</text>
          </view>
          <text :class="['st-badge', statusClass(c.status)]">{{ c.status_label }}</text>
        </view>
        <view class="c-meta">
          <text class="meta-item">🕒 {{ c.activity_time }}</text>
          <text class="meta-item">👤 {{ c.participant_count }}/{{ c.max_players }}</text>
          <text class="meta-item">{{ c.mode === 'fixed' ? '🎯 固定队伍' : '🎲 自由组队' }}</text>
        </view>
      </view>
    </view>

    <!-- 悬浮创建按钮 -->
    <view class="fab" @click="openCreate">
      <text class="fab-plus">+</text>
    </view>

    <!-- 创建弹窗 -->
    <view v-if="showCreate" class="mask" @click="showCreate = false">
      <view class="modal" @click.stop>
        <text class="modal-title">发起约战</text>
        <scroll-view scroll-y class="modal-body">
          <view class="field">
            <text class="field-label">活动名称 *</text>
            <input class="f-input" v-model="form.name" placeholder="如：周五晚8点内战" :maxlength="40" />
          </view>
          <view class="field">
            <text class="field-label">活动说明</text>
            <textarea class="f-textarea" v-model="form.description" placeholder="补充说明（选填）" :maxlength="200" />
          </view>
          <view class="field row">
            <view class="half">
              <text class="field-label">日期 *</text>
              <picker mode="date" :value="form.date" @change="onDate">
                <view class="f-input picker">{{ form.date || '选择日期' }}</view>
              </picker>
            </view>
            <view class="half">
              <text class="field-label">时间</text>
              <picker mode="time" :value="form.time" @change="onTime">
                <view class="f-input picker">{{ form.time }}</view>
              </picker>
            </view>
          </view>
          <view class="field row">
            <view class="half">
              <text class="field-label">最低段位</text>
              <picker :range="rankOptions" :value="form.rankTierMin" @change="onRankMin">
                <view class="f-input picker">{{ rankOptions[form.rankTierMin] }}</view>
              </picker>
            </view>
            <view class="half">
              <text class="field-label">最高段位</text>
              <picker :range="rankOptions" :value="form.rankTierMax" @change="onRankMax">
                <view class="f-input picker">{{ rankOptions[form.rankTierMax] }}</view>
              </picker>
            </view>
          </view>
          <view class="field row">
            <view class="half">
              <text class="field-label">模式</text>
              <picker :range="['自由组队', '固定队伍']" :value="form.mode === 'free' ? 0 : 1" @change="onMode">
                <view class="f-input picker">{{ form.mode === 'free' ? '🎲 自由组队' : '🎯 固定队伍' }}</view>
              </picker>
            </view>
            <view class="half">
              <text class="field-label">人数上限</text>
              <picker :range="playerOptions" @change="onPlayers">
                <view class="f-input picker">{{ form.maxPlayers }} 人 ({{ form.maxPlayers / 2 }}v{{ form.maxPlayers / 2 }})</view>
              </picker>
            </view>
          </view>
          <view class="field" v-if="form.mode === 'fixed'">
            <view class="row">
              <view class="half">
                <text class="field-label">队伍A名称 *</text>
                <input class="f-input" v-model="form.teamA" placeholder="如：猛男队" :maxlength="12" />
              </view>
              <view class="half">
                <text class="field-label">队伍B名称 *</text>
                <input class="f-input" v-model="form.teamB" placeholder="如：咸鱼队" :maxlength="12" />
              </view>
            </view>
          </view>
          <view class="field switch-row">
            <text class="field-label">我也参加</text>
            <switch :checked="form.selfJoin" color="#d4a843" @change="onSelfJoin" style="transform:scale(.8)" />
          </view>
        </scroll-view>
        <view class="modal-actions">
          <view class="m-btn ghost" @click="showCreate = false"><text class="m-text ghost-t">取消</text></view>
          <view class="m-btn primary" :class="{ disabled: creating }" @click="submitCreate">
            <text class="m-text primary-t">{{ creating ? '创建中...' : '创建' }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.challenge-page { min-height: 100vh; padding: 24rpx 24rpx 40rpx; box-sizing: border-box; }
.seg-tabs { display: flex; gap: 4rpx; background: var(--bg); border: 1rpx solid var(--border); border-radius: var(--r); padding: 6rpx; margin-bottom: 24rpx; }
.seg-tab { flex: 1; text-align: center; padding: 16rpx 0; font-size: 28rpx; font-weight: 700; color: var(--ink-3); border-radius: var(--r-sm); transition: all .2s ease; }
.seg-tab.active { background: var(--accent-soft); color: var(--accent); }

.loading-state { display: flex; justify-content: center; padding: 200rpx 0; }
.spinner { width: 52rpx; height: 52rpx; border: 4rpx solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.list-area { padding-bottom: 160rpx; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 10rpx; padding: 160rpx 40rpx; }
.empty-icon { font-size: 72rpx; }
.empty-title { font-size: 30rpx; font-weight: 700; color: var(--ink-1); }
.empty-sub { font-size: 24rpx; color: var(--ink-3); }

.card { background: var(--bg); border: 1rpx solid var(--border); border-radius: var(--r); padding: 28rpx; margin-bottom: 20rpx; }
.card:active { border-color: var(--border-light); }
.card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12rpx; margin-bottom: 12rpx; }
.name-wrap { display: flex; align-items: center; gap: 10rpx; min-width: 0; flex-wrap: wrap; }
.c-name { font-size: 32rpx; font-weight: 800; color: var(--ink-1); word-break: break-all; }
.creator-badge { font-size: 19rpx; font-weight: 700; color: var(--accent); background: var(--accent-soft); padding: 2rpx 12rpx; border-radius: var(--r-sm); flex-shrink: 0; }
.st-badge { font-size: 21rpx; font-weight: 700; padding: 4rpx 14rpx; border-radius: var(--r-sm); flex-shrink: 0; }
.st-open { color: var(--up); background: rgba(63, 185, 80, .1); }
.st-full { color: var(--accent); background: var(--accent-soft); }
.st-ended { color: var(--ink-3); background: rgba(156, 147, 132, .1); }
.st-cancelled { color: var(--down); background: rgba(248, 81, 73, .08); }
.c-desc { font-size: 24rpx; color: var(--ink-2); margin-bottom: 12rpx; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.c-meta { display: flex; flex-wrap: wrap; gap: 8rpx 24rpx; margin-top: 8rpx; }
.meta-item { font-size: 22rpx; color: var(--ink-3); }
.meta-item.creator { color: var(--up); font-weight: 700; }

.fab { position: fixed; right: 40rpx; bottom: 200rpx; width: 108rpx; height: 108rpx; border-radius: 50%; background: var(--accent); display: flex; align-items: center; justify-content: center; box-shadow: 0 8rpx 24rpx rgba(212, 168, 67, .35); z-index: 10; }
.fab:active { transform: scale(.94); }
.fab-plus { font-size: 56rpx; font-weight: 700; color: var(--on-accent); line-height: 1; margin-top: -6rpx; }

/* ── 创建弹窗 ── */
.mask { position: fixed; inset: 0; background: rgba(0, 0, 0, .6); z-index: 100; display: flex; align-items: flex-end; }
.modal { width: 100%; max-height: 88vh; background: var(--bg); border-radius: 28rpx 28rpx 0 0; padding: 32rpx 32rpx 40rpx; box-sizing: border-box; display: flex; flex-direction: column; }
.modal-title { font-size: 34rpx; font-weight: 800; color: var(--ink-1); margin-bottom: 24rpx; }
.modal-body { max-height: 60vh; }
.field { margin-bottom: 24rpx; }
.field.row, .row { display: flex; gap: 16rpx; }
.half { flex: 1; min-width: 0; }
.field-label { display: block; font-size: 23rpx; color: var(--ink-3); margin-bottom: 10rpx; font-weight: 600; }
.f-input { background: var(--panel-2); border: 1rpx solid var(--border); border-radius: var(--r-sm); padding: 0 20rpx; height: 76rpx; line-height: 76rpx; font-size: 26rpx; color: var(--ink-1); width: 100%; box-sizing: border-box; }
.f-input.picker { color: var(--ink-1); }
.f-textarea { background: var(--panel-2); border: 1rpx solid var(--border); border-radius: var(--r-sm); padding: 18rpx 20rpx; font-size: 26rpx; color: var(--ink-1); width: 100%; height: 120rpx; box-sizing: border-box; }
.switch-row { display: flex; justify-content: space-between; align-items: center; }
.switch-row .field-label { margin-bottom: 0; }
.modal-actions { display: flex; gap: 16rpx; margin-top: 8rpx; }
.m-btn { flex: 1; padding: 22rpx 0; border-radius: var(--r); text-align: center; }
.m-btn:active { opacity: .8; }
.m-btn.ghost { background: var(--panel-2); border: 1rpx solid var(--border); }
.m-btn.primary { background: var(--accent); }
.m-btn.primary.disabled { opacity: .6; }
.m-text { font-size: 28rpx; font-weight: 700; }
.ghost-t { color: var(--ink-2); }
.primary-t { color: var(--on-accent); }
</style>
