<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api, extractErr } from '../../api/index.js'
import { heroImg } from '../../utils/image.js'
import RadarChart from '../../components/RadarChart.vue'

const id = ref('')
const detail = ref(null)
const matches = ref([])
const loading = ref(true)
const bound = ref(null)

// 录入弹窗
const showAdd = ref(false)
const matchInput = ref('')
const adding = ref(false)

onLoad((options) => {
  id.value = options.id
  Promise.all([loadDetail(), loadMatches()])
    .finally(() => { loading.value = false })
  api.getMyProfile().then((p) => { bound.value = !!p.bound }).catch(() => {})
})

async function loadDetail() {
  try {
    detail.value = await api.getChallengeDetail(id.value)
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none' })
  }
}

async function loadMatches() {
  try {
    const res = await api.listChallengeMatches(id.value)
    matches.value = res.matches || []
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none' })
  }
}

const canAdd = computed(() => detail.value && detail.value.is_creator)

function fmtDuration(sec) {
  if (!sec) return '--'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function sideText(p) {
  if (!p) return ''
  return p.is_radiant ? '天辉' : '夜魇'
}
function resultText(p) {
  return p.is_winner ? '胜' : '负'
}
function resultClass(p) {
  return p.is_winner ? 'r-win' : 'r-lose'
}

function openAdd() {
  matchInput.value = ''
  showAdd.value = true
}

async function submitAdd() {
  const v = (matchInput.value || '').trim()
  if (!v) return uni.showToast({ title: '请输入比赛ID', icon: 'none' })
  const num = Number(v)
  if (!Number.isInteger(num) || num <= 0) {
    return uni.showToast({ title: '比赛ID应为正整数', icon: 'none' })
  }
  if (adding.value) return
  adding.value = true
  try {
    await api.addChallengeMatch(id.value, num)
    showAdd.value = false
    uni.showToast({ title: '已录入', icon: 'success' })
    loadMatches()
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none', duration: 2500 })
  } finally {
    adding.value = false
  }
}

function removeMatch(m) {
  uni.showModal({
    title: '移除比赛',
    content: `确认移除比赛 ${m.match_id}？`,
    confirmColor: '#f85149',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await api.removeChallengeMatch(id.value, m.match_id)
        uni.showToast({ title: '已移除', icon: 'success' })
        loadMatches()
      } catch (e) {
        uni.showToast({ title: extractErr(e), icon: 'none' })
      }
    },
  })
}

// 把每场比赛的 player 按天辉/夜魇分组，且参与者优先排前
function splitSides(players) {
  if (!players) return { radiant: [], dire: [] }
  const sortFn = (a, b) => Number(b.is_participant) - Number(a.is_participant)
  const radiant = players.filter((p) => p.is_radiant).sort(sortFn)
  const dire = players.filter((p) => !p.is_radiant).sort(sortFn)
  return { radiant, dire }
}
</script>

<template>
  <view class="match-page">
    <view v-if="loading" class="loading-state">
      <view class="spinner"></view>
    </view>

    <template v-else>
      <!-- 顶部信息 -->
      <view v-if="detail" class="card head-card">
        <view class="head-row">
          <text class="h-name">{{ detail.name }}</text>
          <text class="h-sub">{{ matches.length }} 场比赛</text>
        </view>
        <text class="h-tip">发起人录入比赛ID后，自动按 Steam account_id 匹配场上队员</text>
      </view>

      <!-- 录入入口（仅发起人） -->
      <view v-if="canAdd" class="add-bar">
        <view class="a-btn primary" @click="openAdd">
          <text class="a-text on-primary">+ 录入比赛</text>
        </view>
      </view>

      <!-- 比赛列表 -->
      <view v-if="!matches.length && !loading" class="empty">
        <text class="empty-icon">📋</text>
        <text class="empty-title">还没有录入比赛</text>
        <text v-if="canAdd" class="empty-sub">点上方按钮录入第一场</text>
        <text v-else class="empty-sub">等发起人录入后这里会显示队员六星图</text>
      </view>

      <view v-for="m in matches" :key="m.match_id" class="card match-card">
        <!-- 比赛头 -->
        <view class="m-head">
          <text class="m-id">比赛 #{{ m.match_id }}</text>
          <view v-if="!m.error" class="m-result">
            <text :class="['side-tag', m.radiant_win ? 'ta-win' : 'tb-win']">
              {{ m.radiant_win ? '天辉胜' : '夜魇胜' }}
            </text>
            <text class="m-dur">{{ fmtDuration(m.duration) }}</text>
            <text class="m-score">{{ m.radiant_score }} : {{ m.dire_score }}</text>
          </view>
          <view v-else><text class="m-err">{{ m.error }}</text></view>
        </view>

        <!-- 队员六星图 -->
        <template v-if="!m.error">
          <view
            v-for="(side, sideIdx) in [splitSides(m.players).radiant, splitSides(m.players).dire]"
            :key="sideIdx"
            class="side-block"
          >
            <view class="side-head">
              <text :class="['side-name', sideIdx === 0 ? 'sn-r' : 'sn-d']">
                {{ sideIdx === 0 ? '天辉' : '夜魇' }}
              </text>
              <text class="side-count">{{ side.length }} 人</text>
            </view>
            <view v-for="p in side" :key="(p.account_id || '') + p.hero_id" :class="['p-card', { mine: p.is_participant }]">
              <view class="p-top">
                <image class="p-hero" :src="heroImg(p.hero_icon)" mode="aspectFit" />
                <view class="p-info">
                  <view class="p-name-row">
                    <text class="p-name">{{ p.player_name }}</text>
                    <text v-if="p.is_participant" class="mine-badge">本局</text>
                    <text :class="['r-tag', resultClass(p)]">{{ resultText(p) }}</text>
                  </view>
                  <text class="p-hero-name">{{ p.hero_name }} · {{ sideText(p) }}</text>
                  <text class="p-stats">
                    {{ p.kills }}/{{ p.deaths }}/{{ p.assists }} · GPM {{ p.gpm }} · 伤 {{ p.hero_damage }}
                  </text>
                </view>
              </view>
              <RadarChart class="p-radar" :scores="p.radar" :size="160" />
            </view>
          </view>
        </template>

        <!-- 发起人可移除 -->
        <view v-if="canAdd && !m.error" class="m-foot">
          <view class="rm-btn" @click="removeMatch(m)"><text class="rm-text">移除</text></view>
        </view>
      </view>
    </template>

    <!-- 录入弹窗 -->
    <view v-if="showAdd" class="mask" @click="showAdd = false">
      <view class="modal" @click.stop>
        <text class="modal-title">录入比赛ID</text>
        <view class="field">
          <text class="field-label">Dota 2 比赛ID（必须是公开比赛）</text>
          <input class="f-input" type="number" v-model="matchInput" placeholder="如 7890123456" :maxlength="12" />
        </view>
        <text class="modal-tip">录入后会自动拉取比赛数据，按队员绑定的 Steam ID 匹配场上对应玩家</text>
        <view class="modal-actions">
          <view class="m-btn ghost" @click="showAdd = false"><text class="m-text ghost-t">取消</text></view>
          <view class="m-btn primary" :class="{ disabled: adding }" @click="submitAdd">
            <text class="m-text primary-t">{{ adding ? '录入中...' : '确认录入' }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.match-page { min-height: 100vh; padding: 24rpx 24rpx 60rpx; box-sizing: border-box; }
.loading-state { display: flex; justify-content: center; padding: 300rpx 0; }
.spinner { width: 52rpx; height: 52rpx; border: 4rpx solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.card { background: var(--bg); border: 1rpx solid var(--border); border-radius: var(--r); padding: 28rpx; margin-bottom: 20rpx; }

.head-card { padding: 32rpx 28rpx; }
.head-row { display: flex; justify-content: space-between; align-items: baseline; gap: 12rpx; }
.h-name { font-size: 34rpx; font-weight: 800; color: var(--ink-1); word-break: break-all; }
.h-sub { font-size: 23rpx; color: var(--ink-3); flex-shrink: 0; }
.h-tip { font-size: 21rpx; color: var(--ink-3); line-height: 1.5; margin-top: 12rpx; display: block; }

.add-bar { margin-bottom: 20rpx; }
.a-btn { padding: 22rpx 0; border-radius: var(--r); text-align: center; }
.a-btn:active { opacity: .8; }
.a-btn.primary { background: var(--accent); }
.a-text { font-size: 27rpx; font-weight: 700; }
.on-primary { color: var(--on-accent); }

.empty { display: flex; flex-direction: column; align-items: center; gap: 10rpx; padding: 140rpx 40rpx; }
.empty-icon { font-size: 72rpx; }
.empty-title { font-size: 28rpx; font-weight: 700; color: var(--ink-1); }
.empty-sub { font-size: 22rpx; color: var(--ink-3); }

.match-card { padding: 24rpx; }
.m-head { display: flex; justify-content: space-between; align-items: center; gap: 12rpx; margin-bottom: 16rpx; flex-wrap: wrap; }
.m-id { font-size: 26rpx; font-weight: 800; color: var(--ink-1); }
.m-result { display: flex; align-items: center; gap: 12rpx; flex-wrap: wrap; }
.side-tag { font-size: 20rpx; font-weight: 700; padding: 3rpx 12rpx; border-radius: var(--r-sm); }
.ta-win { color: var(--up); background: rgba(63, 185, 80, .12); }
.tb-win { color: var(--down); background: rgba(248, 81, 73, .1); }
.m-dur { font-size: 22rpx; color: var(--ink-3); }
.m-score { font-size: 22rpx; color: var(--ink-2); font-weight: 700; }
.m-err { font-size: 22rpx; color: var(--down); }

.side-block { margin-top: 8rpx; }
.side-head { display: flex; justify-content: space-between; align-items: center; padding: 8rpx 4rpx 12rpx; border-bottom: 1rpx solid var(--border); margin-bottom: 12rpx; }
.side-name { font-size: 24rpx; font-weight: 800; }
.sn-r { color: var(--up); }
.sn-d { color: var(--down); }
.side-count { font-size: 20rpx; color: var(--ink-3); }

.p-card { background: var(--panel-2); border: 1rpx solid transparent; border-radius: var(--r-sm); padding: 18rpx; margin-bottom: 12rpx; }
.p-card.mine { border-color: var(--accent); background: var(--accent-soft); }
.p-top { display: flex; gap: 14rpx; align-items: flex-start; }
.p-hero { width: 64rpx; height: 64rpx; border-radius: var(--r-sm); flex-shrink: 0; background: var(--panel-2); }
.p-info { flex: 1; min-width: 0; }
.p-name-row { display: flex; align-items: center; gap: 8rpx; flex-wrap: wrap; }
.p-name { font-size: 25rpx; font-weight: 700; color: var(--ink-1); max-width: 220rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mine-badge { font-size: 18rpx; font-weight: 700; color: var(--accent); background: var(--accent-soft); padding: 2rpx 10rpx; border-radius: var(--r-sm); }
.r-tag { font-size: 18rpx; font-weight: 700; padding: 2rpx 10rpx; border-radius: var(--r-sm); }
.r-win { color: var(--up); background: rgba(63, 185, 80, .1); }
.r-lose { color: var(--down); background: rgba(248, 81, 73, .08); }
.p-hero-name { font-size: 21rpx; color: var(--ink-3); display: block; margin-top: 2rpx; }
.p-stats { font-size: 20rpx; color: var(--ink-3); display: block; margin-top: 2rpx; }
.p-radar { margin-top: 12rpx; }

.m-foot { display: flex; justify-content: flex-end; margin-top: 8rpx; }
.rm-btn { padding: 10rpx 24rpx; border-radius: var(--r-sm); background: rgba(248, 81, 73, .06); border: 1rpx solid rgba(248, 81, 73, .2); }
.rm-btn:active { opacity: .8; }
.rm-text { font-size: 22rpx; font-weight: 700; color: var(--down); }

/* ── 录入弹窗 ── */
.mask { position: fixed; inset: 0; background: rgba(0, 0, 0, .6); z-index: 100; display: flex; align-items: flex-end; }
.modal { width: 100%; background: var(--bg); border-radius: 28rpx 28rpx 0 0; padding: 32rpx 32rpx 40rpx; box-sizing: border-box; }
.modal-title { font-size: 30rpx; font-weight: 800; color: var(--ink-1); margin-bottom: 24rpx; }
.field { margin-bottom: 20rpx; }
.field-label { display: block; font-size: 23rpx; color: var(--ink-3); margin-bottom: 10rpx; font-weight: 600; }
.f-input { background: var(--panel-2); border: 1rpx solid var(--border); border-radius: var(--r-sm); padding: 0 20rpx; height: 76rpx; line-height: 76rpx; font-size: 26rpx; color: var(--ink-1); width: 100%; box-sizing: border-box; }
.modal-tip { font-size: 21rpx; color: var(--ink-3); line-height: 1.5; display: block; margin-bottom: 20rpx; }
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
