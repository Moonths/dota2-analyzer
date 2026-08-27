<script setup>
import { ref, computed } from 'vue'
import { onLoad, onShareAppMessage } from '@dcloudio/uni-app'
import { api, extractErr } from '../../api/index.js'

const id = ref('')
const detail = ref(null)
const loading = ref(true)
const acting = ref(false)
const bound = ref(null)

// ── 发起人对调模式 ──
const swapMode = ref(false)
const selected = ref([]) // participant ids

// ── 编辑弹窗 ──
const showEdit = ref(false)
const editForm = ref({ name: '', description: '', date: '', time: '20:00' })

// ── 页内绑定弹窗 (空降用户报名用, 绑完自动继续报名) ──
const showBind = ref(false)
const bindInput = ref('')
const binding = ref(false)
const pendingTeam = ref(null) // 绑定完成后要继续的报名: null=自由报名, 0/1=固定队伍

onLoad((options) => {
  id.value = options.id
  load()
  api.getMyProfile().then((p) => { bound.value = !!p.bound }).catch(() => {})
})

// 分享: 空降用户直达本页, 报名时页内弹窗绑定
onShareAppMessage(() => {
  const d = detail.value
  if (!d) return { title: '约战 · 分锅大会', path: `/pages/challenge/detail?id=${id.value}` }
  const need = diff.value > 0 ? `还差 ${diff.value} 人` : '已满员'
  return {
    title: `「${d.name}」${need} · ${d.max_players / 2}v${d.max_players / 2} 快来`,
    path: `/pages/challenge/detail?id=${id.value}`,
  }
})

async function load() {
  try {
    detail.value = await api.getChallengeDetail(id.value)
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none' })
  } finally {
    loading.value = false
  }
}

const canJoin = computed(() => {
  const d = detail.value
  return d && d.status === 'open' && !d.joined
})
const canLeave = computed(() => detail.value && detail.value.joined && detail.value.status !== 'cancelled')
const canShuffle = computed(() => {
  const d = detail.value
  return d && d.is_creator && d.mode === 'free' && d.status === 'full' && !isAssigned.value
})
const isAssigned = computed(() => {
  const d = detail.value
  return d && d.participants.some((p) => p.team >= 0)
})
const teamA = computed(() => (detail.value?.participants || []).filter((p) => p.team === 0))
const teamB = computed(() => (detail.value?.participants || []).filter((p) => p.team === 1))
const unassigned = computed(() => (detail.value?.participants || []).filter((p) => p.team === -1))
const teamCap = computed(() => (detail.value?.max_players || 0) / 2)
const joinedCount = computed(() => detail.value?.participants?.length || 0)
const diff = computed(() => (detail.value?.max_players || 0) - joinedCount.value)
const progPercent = computed(() => {
  const mx = detail.value?.max_players || 1
  return Math.min(100, Math.round(joinedCount.value / mx * 100))
})
// 头像堆叠最多展示 7 个, 超出显示 +N
const MAX_AVATAR_STACK = 7
const unassignedAvatars = computed(() => {
  const list = detail.value?.participants || []
  const shown = list.slice(0, MAX_AVATAR_STACK)
  const extra = list.length - shown.length
  return { shown, extra }
})
const teamAAvatars = computed(() => {
  const list = teamA.value
  const shown = list.slice(0, MAX_AVATAR_STACK)
  const extra = list.length - shown.length
  return { shown, extra }
})
const teamBAvatars = computed(() => {
  const list = teamB.value
  const shown = list.slice(0, MAX_AVATAR_STACK)
  const extra = list.length - shown.length
  return { shown, extra }
})
const progHint = computed(() => {
  const d = detail.value
  if (!d) return ''
  if (d.status === 'cancelled') return '已取消'
  if (d.status === 'ended') return '已结束'
  if (diff.value <= 0) return '已满员'
  return `还差 ${diff.value} 人`
})

const RANK_OPTIONS = ['不限', '先锋', '卫士', '中军', '统帅', '传奇', '万古流芳', '超凡入圣', '不朽']

function rankText() {
  const d = detail.value
  if (!d) return '不限'
  const min = d.rank_tier_min
  const max = d.rank_tier_max
  if (min === null || min === undefined) return '不限'
  const minName = RANK_OPTIONS[Math.floor(min / 10)] || `档位${min}`
  if (max === null || max === undefined) return `${minName}起`
  const maxName = RANK_OPTIONS[Math.floor(max / 10)] || `档位${max}`
  if (Math.floor(min / 10) === Math.floor(max / 10)) return minName
  return `${minName} ~ ${maxName}`
}
function statusClass(s) {
  return { open: 'st-open', full: 'st-full', ended: 'st-ended', cancelled: 'st-cancelled' }[s] || 'st-ended'
}
function rankOrUnknown(p) {
  return p.rank_name || '段位未知'
}

function needBind(team = null) {
  // 页内弹窗绑定, 绑完自动继续报名 (不再 switchTab 跳走, 空降用户不流失)
  pendingTeam.value = team
  bindInput.value = ''
  showBind.value = true
}

async function submitBind() {
  const input = bindInput.value.trim()
  if (!input) return uni.showToast({ title: '请输入 Steam ID', icon: 'none' })
  if (binding.value) return
  binding.value = true
  try {
    await api.bindSteam(input)
    bound.value = true
    showBind.value = false
    uni.showToast({ title: '绑定成功', icon: 'success' })
    // 自动继续被拦截的报名
    const team = pendingTeam.value
    pendingTeam.value = null
    setTimeout(() => confirmJoin(team), 400)
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none', duration: 2500 })
  } finally {
    binding.value = false
  }
}

// ── 报名 ──
function joinFree() {
  if (bound.value === false) return needBind(null)
  confirmJoin(null)
}
function joinTeam(team) {
  if (bound.value === false) return needBind(team)
  const d = detail.value
  const teamName = team === 0 ? d.team_a_name : d.team_b_name
  uni.showModal({
    title: '加入队伍',
    content: `确定加入「${teamName}」吗？`,
    success: (r) => { if (r.confirm) confirmJoin(team) },
  })
}
async function confirmJoin(team) {
  if (acting.value) return
  acting.value = true
  try {
    await api.joinChallenge(id.value, team)
    uni.showToast({ title: '报名成功', icon: 'success' })
    load()
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none', duration: 2500 })
  } finally {
    acting.value = false
  }
}

// ── 退出 ──
function leave() {
  const d = detail.value
  const tip = d.mode === 'free' && isAssigned.value ? '退出后已分的队伍将重置，需重新分队' : '退出后将空出一个名额'
  uni.showModal({
    title: '退出约战',
    content: tip + '，确定退出吗？',
    confirmText: '退出',
    confirmColor: '#f85149',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await api.leaveChallenge(id.value)
        uni.showToast({ title: '已退出', icon: 'success' })
        load()
      } catch (e) {
        uni.showToast({ title: extractErr(e), icon: 'none' })
      }
    },
  })
}

// ── 换队（固定模式） ──
function switchTo(team) {
  const d = detail.value
  const teamName = team === 0 ? d.team_a_name : d.team_b_name
  uni.showModal({
    title: '换队',
    content: `确定换到「${teamName}」吗？`,
    success: async (r) => {
      if (!r.confirm) return
      try {
        await api.switchTeam(id.value, team)
        uni.showToast({ title: '已换队', icon: 'success' })
        load()
      } catch (e) {
        uni.showToast({ title: extractErr(e), icon: 'none' })
      }
    },
  })
}

// ── 随机分队 ──
function shuffle() {
  uni.showModal({
    title: '随机分队',
    content: '将随机把所有人分成两队，确定吗？',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await api.shuffleTeams(id.value)
        uni.showToast({ title: '分队完成', icon: 'success' })
        load()
      } catch (e) {
        uni.showToast({ title: extractErr(e), icon: 'none' })
      }
    },
  })
}

// ── 对调 ──
function toggleSwapMode() {
  swapMode.value = !swapMode.value
  selected.value = []
}
function tapParticipant(p) {
  if (!swapMode.value) return
  const idx = selected.value.indexOf(p.id)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
    return
  }
  selected.value.push(p.id)
  if (selected.value.length === 2) {
    doSwap(selected.value[0], selected.value[1])
  }
}
async function doSwap(a, b) {
  const [pa, pb] = [a, b].map((pid) => detail.value.participants.find((p) => p.id === pid))
  uni.showModal({
    title: '对调确认',
    content: `把「${pa.steam_name}」和「${pb.steam_name}」互换队伍？`,
    success: async (r) => {
      if (r.confirm) {
        try {
          await api.swapParticipants(id.value, a, b)
          uni.showToast({ title: '已对调', icon: 'success' })
          load()
        } catch (e) {
          uni.showToast({ title: extractErr(e), icon: 'none' })
        }
      }
      selected.value = []
    },
  })
}

// ── 编辑 ──
function openEdit() {
  const d = detail.value
  const [date, time] = d.activity_time.split(' ')
  editForm.value = { name: d.name, description: d.description || '', date, time: time || '20:00' }
  showEdit.value = true
}

// ── 比赛回顾 ──
function openMatch() {
  uni.navigateTo({ url: `/pages/challenge/match?id=${id.value}` })
}
function onEditDate(e) { editForm.value.date = e.detail.value }
function onEditTime(e) { editForm.value.time = e.detail.value }
async function submitEdit() {
  const f = editForm.value
  if (!f.name.trim()) return uni.showToast({ title: '名称不能为空', icon: 'none' })
  try {
    await api.updateChallenge(id.value, {
      name: f.name.trim(),
      description: f.description.trim(),
      activity_time: `${f.date} ${f.time}`,
    })
    showEdit.value = false
    uni.showToast({ title: '已保存', icon: 'success' })
    load()
  } catch (e) {
    uni.showToast({ title: extractErr(e), icon: 'none' })
  }
}

// ── 取消 ──
function cancelChallenge() {
  uni.showModal({
    title: '取消约战',
    content: '取消后所有参与者将看到「已取消」，确定吗？',
    confirmText: '取消约战',
    confirmColor: '#f85149',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await api.cancelChallenge(id.value)
        uni.showToast({ title: '已取消', icon: 'success' })
        load()
      } catch (e) {
        uni.showToast({ title: extractErr(e), icon: 'none' })
      }
    },
  })
}
</script>

<template>
  <view class="detail-page">
    <view v-if="loading" class="loading-state">
      <view class="spinner"></view>
    </view>

    <template v-else-if="detail">
      <!-- 信息卡 -->
      <view class="card info-card">
        <view class="card-top">
          <text class="c-name">{{ detail.name }}</text>
          <text :class="['st-badge', statusClass(detail.status)]">{{ detail.status_label }}</text>
        </view>
        <text v-if="detail.description" class="c-desc">{{ detail.description }}</text>
        <view class="info-rows">
          <view class="info-row"><text class="i-label">时间</text><text class="i-val">{{ detail.activity_time }}</text></view>
          <view class="info-row">
            <text class="i-label">模式</text>
            <text class="i-val">{{ detail.mode === 'fixed' ? '固定队伍' : '自由组队' }} · {{ detail.max_players / 2 }}v{{ detail.max_players / 2 }}</text>
          </view>
          <view class="info-row"><text class="i-label">段位</text><text class="i-val">{{ rankText() }}</text></view>
          <view class="info-row"><text class="i-label">发起人</text><text class="i-val">{{ detail.creator_name }}</text></view>
        </view>
        <!-- 报名进度 -->
        <view class="prog-block">
          <view class="prog-head">
            <text class="prog-label">报名进度</text>
            <text class="prog-count">{{ joinedCount }}/{{ detail.max_players }}</text>
            <text :class="['prog-hint', { full: diff <= 0 }]">{{ progHint }}</text>
          </view>
          <view class="prog-track">
            <view class="prog-bar" :style="{ width: progPercent + '%' }"></view>
          </view>
          <!-- 未分队: 单行头像堆叠 -->
          <view v-if="!isAssigned" class="avatar-stack">
            <view v-for="(p, i) in unassignedAvatars.shown" :key="p.id" class="stack-avatar" :style="{ left: i * 28 + 'rpx', zIndex: 10 - i }">
              <image class="stack-img" :src="p.avatar" mode="aspectFill" />
            </view>
            <view v-if="unassignedAvatars.extra > 0" class="stack-avatar stack-extra" :style="{ left: unassignedAvatars.shown.length * 28 + 'rpx' }">
              <text class="stack-extra-text">+{{ unassignedAvatars.extra }}</text>
            </view>
            <view v-if="!joinedCount" class="stack-empty"><text class="stack-empty-text">还没有人报名</text></view>
          </view>
          <!-- 已分队: 双方对垒头像 -->
          <view v-else class="versus-stack">
            <view class="vs-col">
              <view class="vs-team-name ta">{{ detail.team_a_name }}</view>
              <view class="vs-stack-row">
                <view v-for="(p, i) in teamAAvatars.shown" :key="p.id" class="stack-avatar ta-ring" :style="{ left: i * 28 + 'rpx', zIndex: 10 - i }">
                  <image class="stack-img" :src="p.avatar" mode="aspectFill" />
                </view>
                <view v-if="teamAAvatars.extra > 0" class="stack-avatar stack-extra" :style="{ left: teamAAvatars.shown.length * 28 + 'rpx' }">
                  <text class="stack-extra-text">+{{ teamAAvatars.extra }}</text>
                </view>
                <view v-if="!teamA.length" class="stack-empty-mini"><text class="stack-empty-text">暂无</text></view>
              </view>
            </view>
            <view class="vs-center"><text class="vs-text">VS</text></view>
            <view class="vs-col">
              <view class="vs-team-name tb">{{ detail.team_b_name }}</view>
              <view class="vs-stack-row">
                <view v-for="(p, i) in teamBAvatars.shown" :key="p.id" class="stack-avatar tb-ring" :style="{ left: i * 28 + 'rpx', zIndex: 10 - i }">
                  <image class="stack-img" :src="p.avatar" mode="aspectFill" />
                </view>
                <view v-if="teamBAvatars.extra > 0" class="stack-avatar stack-extra" :style="{ left: teamBAvatars.shown.length * 28 + 'rpx' }">
                  <text class="stack-extra-text">+{{ teamBAvatars.extra }}</text>
                </view>
                <view v-if="!teamB.length" class="stack-empty-mini"><text class="stack-empty-text">暂无</text></view>
              </view>
            </view>
          </view>
        </view>

        <view v-if="swapMode" class="swap-tip">
          <text class="swap-tip-text">调整模式: 依次点击两人即可对调队伍，点同一人取消选择</text>
        </view>
      </view>

      <!-- 比赛回顾入口 -->
      <view class="card recap-entry" @click="openMatch">
        <view class="recap-row">
          <text class="recap-icon">⚔️</text>
          <view class="recap-info">
            <text class="recap-title">比赛回顾</text>
            <text class="recap-sub">录入比赛ID · 查看每个队员六星图</text>
          </view>
          <text class="recap-arrow">›</text>
        </view>
      </view>

      <!-- 参与者 -->
      <view class="card">
        <view class="section-head">
          <text class="section-title">参与者 {{ detail.participants.length }}/{{ detail.max_players }}</text>
          <text v-if="detail.mode === 'free' && !isAssigned && detail.status === 'open'" class="section-sub">满员后发起人随机分队</text>
        </view>

        <!-- 未分队（自由模式报名中） -->
        <view v-if="!isAssigned" class="unassigned-list">
          <view v-if="!detail.participants.length" class="no-p"><text class="no-p-text">还没有人报名</text></view>
          <view v-for="p in unassigned" :key="p.id" class="p-row">
            <image class="p-avatar" :src="p.avatar" mode="aspectFill" />
            <view class="p-info">
              <text class="p-name">{{ p.steam_name }}</text>
              <text class="p-sub">{{ rankOrUnknown(p) }}</text>
            </view>
            <text v-if="p.openid === detail.creator_openid" class="creator-badge">发起人</text>
          </view>
        </view>

        <!-- 已分队 -->
        <view v-else class="teams">
          <view class="team-col">
            <view class="team-head">
              <text class="team-name ta">{{ detail.team_a_name }}</text>
              <text class="team-count">{{ teamA.length }}/{{ teamCap }}</text>
            </view>
            <view v-for="p in teamA" :key="p.id" :class="['p-row', { selecting: selected.includes(p.id) }]" @click="tapParticipant(p)">
              <image class="p-avatar" :src="p.avatar" mode="aspectFill" />
              <view class="p-info">
                <text class="p-name">{{ p.steam_name }}</text>
                <text class="p-sub">{{ rankOrUnknown(p) }}</text>
              </view>
              <text v-if="p.openid === detail.creator_openid" class="creator-badge">发起人</text>
              <text v-if="p.openid === detail.my_openid" class="me-badge">我</text>
            </view>
            <view v-if="!teamA.length" class="no-p"><text class="no-p-text">暂无</text></view>
          </view>
          <view class="vs"><text class="vs-text">VS</text></view>
          <view class="team-col">
            <view class="team-head">
              <text class="team-name tb">{{ detail.team_b_name }}</text>
              <text class="team-count">{{ teamB.length }}/{{ teamCap }}</text>
            </view>
            <view v-for="p in teamB" :key="p.id" :class="['p-row', { selecting: selected.includes(p.id) }]" @click="tapParticipant(p)">
              <image class="p-avatar" :src="p.avatar" mode="aspectFill" />
              <view class="p-info">
                <text class="p-name">{{ p.steam_name }}</text>
                <text class="p-sub">{{ rankOrUnknown(p) }}</text>
              </view>
              <text v-if="p.openid === detail.creator_openid" class="creator-badge">发起人</text>
              <text v-if="p.openid === detail.my_openid" class="me-badge">我</text>
            </view>
            <view v-if="!teamB.length" class="no-p"><text class="no-p-text">暂无</text></view>
          </view>
        </view>
      </view>

      <!-- 操作区 -->
      <view class="actions">
        <!-- 参与者: 未报名 + 可报名 -->
        <template v-if="!detail.is_creator">
          <view v-if="canJoin && detail.mode === 'free'" class="a-btn primary" @click="joinFree">
            <text class="a-text on-primary">{{ acting ? '报名中...' : '报名参加' }}</text>
          </view>
          <template v-if="canJoin && detail.mode === 'fixed'">
            <view class="a-btn team-btn ta-border" @click="joinTeam(0)">
              <text class="a-text ta-text">加入{{ detail.team_a_name }}({{ teamA.length }}/{{ teamCap }})</text>
            </view>
            <view class="a-btn team-btn tb-border" @click="joinTeam(1)">
              <text class="a-text tb-text">加入{{ detail.team_b_name }}({{ teamB.length }}/{{ teamCap }})</text>
            </view>
          </template>
          <view v-if="canLeave && detail.mode === 'fixed' && isAssigned" class="a-btn ghost" @click="switchTo(detail.my_team === 0 ? 1 : 0)">
            <text class="a-text ghost-text">换到{{ detail.my_team === 0 ? detail.team_b_name : detail.team_a_name }}</text>
          </view>
          <view v-if="canLeave" class="a-btn danger" @click="leave">
            <text class="a-text danger-text">退出约战</text>
          </view>
          <view v-if="detail.status === 'full' && !detail.joined" class="a-btn disabled-btn">
            <text class="a-text disabled-text">已满员</text>
          </view>
          <view v-if="detail.status === 'cancelled'" class="a-btn disabled-btn">
            <text class="a-text disabled-text">已取消</text>
          </view>
          <view v-if="detail.status === 'ended'" class="a-btn disabled-btn">
            <text class="a-text disabled-text">{{ detail.status_label }}</text>
          </view>
        </template>

        <!-- 发起人 -->
        <template v-else>
          <view v-if="canShuffle" class="a-btn primary" @click="shuffle">
            <text class="a-text on-primary">🎲 随机分队</text>
          </view>
          <view v-if="isAssigned && detail.mode === 'free' && detail.status !== 'cancelled'" class="a-btn ghost" @click="toggleSwapMode">
            <text class="a-text ghost-text">{{ swapMode ? '退出调整' : '调整阵容' }}</text>
          </view>
          <view class="a-btn ghost" @click="openEdit"><text class="a-text ghost-text">编辑</text></view>
          <view v-if="detail.status !== 'cancelled' && detail.status !== 'ended'" class="a-btn danger" @click="cancelChallenge">
            <text class="a-text danger-text">取消约战</text>
          </view>
        </template>
      </view>
      <text v-if="detail.my_rank_unknown && detail.joined" class="mmr-tip">你的段位数据未知（OpenDota 未返回），本次已按无数据放行</text>
    </template>

    <!-- 编辑弹窗 -->
    <view v-if="showEdit" class="mask" @click="showEdit = false">
      <view class="modal" @click.stop>
        <text class="modal-title">编辑约战（门槛与人数上限不可改）</text>
        <view class="field">
          <text class="field-label">活动名称</text>
          <input class="f-input" v-model="editForm.name" :maxlength="40" />
        </view>
        <view class="field">
          <text class="field-label">活动说明</text>
          <textarea class="f-textarea" v-model="editForm.description" :maxlength="200" />
        </view>
        <view class="field row">
          <view class="half">
            <text class="field-label">日期</text>
            <picker mode="date" :value="editForm.date" @change="onEditDate">
              <view class="f-input">{{ editForm.date }}</view>
            </picker>
          </view>
          <view class="half">
            <text class="field-label">时间</text>
            <picker mode="time" :value="editForm.time" @change="onEditTime">
              <view class="f-input">{{ editForm.time }}</view>
            </picker>
          </view>
        </view>
        <view class="modal-actions">
          <view class="m-btn ghost" @click="showEdit = false"><text class="m-text ghost-t">取消</text></view>
          <view class="m-btn primary" @click="submitEdit"><text class="m-text primary-t">保存</text></view>
        </view>
      </view>
    </view>

    <!-- 页内绑定弹窗 (空降报名用户) -->
    <view v-if="showBind" class="mask" @click="showBind = false">
      <view class="modal" @click.stop>
        <text class="modal-title">绑定 Steam 账号</text>
        <text class="bind-modal-tip">报名约战需要先绑定 Steam，绑完自动继续报名</text>
        <view class="field">
          <text class="field-label">SteamID64 / 自定义URL ID / 主页链接</text>
          <input
            class="f-input"
            v-model="bindInput"
            placeholder="推荐游戏内个人资料的数字 ID"
            placeholder-class="input-ph"
            :disabled="binding"
          />
        </view>
        <view class="modal-actions">
          <view class="m-btn ghost" @click="showBind = false"><text class="m-text ghost-t">取消</text></view>
          <view class="m-btn primary" :class="{ disabled: binding }" @click="submitBind">
            <text class="m-text primary-t">{{ binding ? '绑定中...' : '绑定并报名' }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.detail-page { min-height: 100vh; padding: 24rpx 24rpx 60rpx; box-sizing: border-box; }
.loading-state { display: flex; justify-content: center; padding: 300rpx 0; }
.spinner { width: 52rpx; height: 52rpx; border: 4rpx solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.card { background: var(--bg); border: 1rpx solid var(--border); border-radius: var(--r); padding: 28rpx; margin-bottom: 20rpx; }
.info-card { padding: 32rpx 28rpx; }
.card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12rpx; }
.c-name { font-size: 36rpx; font-weight: 800; color: var(--ink-1); word-break: break-all; }
.st-badge { font-size: 21rpx; font-weight: 700; padding: 4rpx 14rpx; border-radius: var(--r-sm); flex-shrink: 0; }
.st-open { color: var(--up); background: rgba(63, 185, 80, .1); }
.st-full { color: var(--accent); background: var(--accent-soft); }
.st-ended { color: var(--ink-3); background: rgba(156, 147, 132, .1); }
.st-cancelled { color: var(--down); background: rgba(248, 81, 73, .08); }
.c-desc { font-size: 25rpx; color: var(--ink-2); line-height: 1.6; margin: 16rpx 0 8rpx; }
.info-rows { margin-top: 16rpx; display: flex; flex-direction: column; gap: 10rpx; }
.info-row { display: flex; }
.i-label { width: 110rpx; font-size: 23rpx; color: var(--ink-3); flex-shrink: 0; }
.i-val { font-size: 25rpx; color: var(--ink-1); font-weight: 600; }
.swap-tip { margin-top: 20rpx; background: var(--accent-soft); border-radius: var(--r-sm); padding: 14rpx 18rpx; }
.swap-tip-text { font-size: 22rpx; color: var(--accent); line-height: 1.5; }

/* ── 报名进度 ── */
.prog-block { margin-top: 24rpx; padding-top: 22rpx; border-top: 1rpx solid var(--border); }
.prog-head { display: flex; align-items: baseline; gap: 14rpx; }
.prog-label { font-size: 23rpx; color: var(--ink-3); font-weight: 600; }
.prog-count { font-size: 32rpx; font-weight: 800; color: var(--ink-1); margin-right: auto; }
.prog-hint { font-size: 22rpx; font-weight: 700; color: var(--ink-3); }
.prog-hint.full { color: var(--up); }
.prog-track { margin-top: 14rpx; height: 12rpx; background: var(--panel-2); border-radius: 999rpx; overflow: hidden; }
.prog-bar { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent)); border-radius: 999rpx; transition: width .3s ease; }

/* 头像堆叠 */
.avatar-stack { position: relative; height: 64rpx; margin-top: 18rpx; }
.versus-stack { display: flex; align-items: flex-start; gap: 16rpx; margin-top: 18rpx; }
.vs-col { flex: 1; min-width: 0; }
.vs-team-name { font-size: 22rpx; font-weight: 800; margin-bottom: 8rpx; }
.vs-team-name.ta { color: var(--up); }
.vs-team-name.tb { color: var(--down); }
.vs-stack-row { position: relative; height: 64rpx; }
.vs-center { align-self: center; padding-top: 28rpx; }
.vs-text { font-size: 22rpx; font-weight: 800; color: var(--ink-3); }

.stack-avatar { position: absolute; top: 0; width: 56rpx; height: 56rpx; border-radius: 50%; overflow: hidden; background: var(--panel-2); border: 2rpx solid var(--bg); box-sizing: border-box; }
.stack-img { width: 100%; height: 100%; }
.stack-extra { display: flex; align-items: center; justify-content: center; background: var(--panel-2); border: 2rpx solid var(--border); }
.stack-extra-text { font-size: 20rpx; font-weight: 700; color: var(--ink-2); }
.stack-avatar.ta-ring { border-color: rgba(63, 185, 80, .55); }
.stack-avatar.tb-ring { border-color: rgba(248, 81, 73, .55); }
.stack-empty { position: absolute; top: 50%; left: 0; transform: translateY(-50%); }
.stack-empty-mini { position: absolute; top: 50%; left: 0; transform: translateY(-50%); }
.stack-empty-text { font-size: 22rpx; color: var(--ink-3); }

.recap-entry { padding: 24rpx 28rpx; }
.recap-entry:active { border-color: var(--accent); }
.recap-row { display: flex; align-items: center; gap: 16rpx; }
.recap-icon { font-size: 36rpx; }
.recap-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2rpx; }
.recap-title { font-size: 28rpx; font-weight: 800; color: var(--ink-1); }
.recap-sub { font-size: 21rpx; color: var(--ink-3); }
.recap-arrow { font-size: 40rpx; color: var(--ink-3); font-weight: 700; line-height: 1; }

.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20rpx; }
.section-title { font-size: 28rpx; font-weight: 800; color: var(--ink-1); }
.section-sub { font-size: 21rpx; color: var(--ink-3); }

.unassigned-list { display: flex; flex-direction: column; gap: 14rpx; }
.p-row { display: flex; align-items: center; gap: 16rpx; background: var(--panel-2); border-radius: var(--r-sm); padding: 14rpx 16rpx; border: 2rpx solid transparent; }
.p-row.selecting { border-color: var(--accent); background: var(--accent-soft); }
.p-avatar { width: 76rpx; height: 76rpx; border-radius: var(--r-sm); flex-shrink: 0; background: var(--panel-2); }
.p-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2rpx; }
.p-name { font-size: 26rpx; font-weight: 700; color: var(--ink-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p-sub { font-size: 21rpx; color: var(--ink-3); }
.creator-badge { font-size: 19rpx; font-weight: 700; color: var(--accent); background: var(--accent-soft); padding: 2rpx 12rpx; border-radius: var(--r-sm); flex-shrink: 0; }
.me-badge { font-size: 19rpx; font-weight: 700; color: var(--up); background: rgba(63, 185, 80, .1); padding: 2rpx 12rpx; border-radius: var(--r-sm); flex-shrink: 0; }
.no-p { padding: 24rpx 0; text-align: center; }
.no-p-text { font-size: 23rpx; color: var(--ink-3); }

.teams { display: flex; gap: 12rpx; align-items: flex-start; }
.team-col { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12rpx; }
.team-head { display: flex; justify-content: space-between; align-items: center; padding: 0 4rpx 4rpx; }
.team-name { font-size: 26rpx; font-weight: 800; }
.team-name.ta { color: var(--up); }
.team-name.tb { color: var(--down); }
.team-count { font-size: 21rpx; color: var(--ink-3); }
.vs { align-self: center; padding: 0 4rpx; }
.vs-text { font-size: 22rpx; font-weight: 800; color: var(--ink-3); }

.actions { display: flex; flex-wrap: wrap; gap: 16rpx; }
.a-btn { flex: 1; min-width: 200rpx; padding: 24rpx 0; border-radius: var(--r); text-align: center; }
.a-btn:active { opacity: .8; }
.a-btn.primary { background: var(--accent); }
.a-btn.ghost { background: var(--panel-2); border: 1rpx solid var(--border); }
.a-btn.danger { background: rgba(248, 81, 73, .06); border: 1rpx solid rgba(248, 81, 73, .2); }
.a-btn.disabled-btn { background: var(--panel-2); opacity: .7; }
.a-btn.team-btn { background: var(--panel-2); border: 2rpx solid; }
.ta-border { border-color: rgba(63, 185, 80, .35); }
.tb-border { border-color: rgba(248, 81, 73, .35); }
.a-text { font-size: 27rpx; font-weight: 700; }
.on-primary { color: var(--on-accent); }
.ghost-text { color: var(--ink-2); }
.danger-text { color: var(--down); }
.disabled-text { color: var(--ink-3); }
.ta-text { color: var(--up); font-size: 24rpx; }
.tb-text { color: var(--down); font-size: 24rpx; }
.mmr-tip { display: block; text-align: center; font-size: 21rpx; color: var(--ink-3); margin-top: 20rpx; }

/* ── 编辑弹窗 ── */
.mask { position: fixed; inset: 0; background: rgba(0, 0, 0, .6); z-index: 100; display: flex; align-items: flex-end; }
.modal { width: 100%; background: var(--bg); border-radius: 28rpx 28rpx 0 0; padding: 32rpx 32rpx 40rpx; box-sizing: border-box; }
.modal-title { font-size: 30rpx; font-weight: 800; color: var(--ink-1); margin-bottom: 24rpx; }
.field { margin-bottom: 24rpx; }
.field.row, .row { display: flex; gap: 16rpx; }
.half { flex: 1; min-width: 0; }
.field-label { display: block; font-size: 23rpx; color: var(--ink-3); margin-bottom: 10rpx; font-weight: 600; }
.f-input { background: var(--panel-2); border: 1rpx solid var(--border); border-radius: var(--r-sm); padding: 0 20rpx; height: 76rpx; line-height: 76rpx; font-size: 26rpx; color: var(--ink-1); width: 100%; box-sizing: border-box; }
.f-textarea { background: var(--panel-2); border: 1rpx solid var(--border); border-radius: var(--r-sm); padding: 18rpx 20rpx; font-size: 26rpx; color: var(--ink-1); width: 100%; height: 120rpx; box-sizing: border-box; }
.modal-actions { display: flex; gap: 16rpx; margin-top: 8rpx; }
.m-btn { flex: 1; padding: 22rpx 0; border-radius: var(--r); text-align: center; }
.m-btn:active { opacity: .8; }
.m-btn.ghost { background: var(--panel-2); border: 1rpx solid var(--border); }
.m-btn.primary { background: var(--accent); }
.m-btn.disabled { opacity: .6; }
.m-text { font-size: 28rpx; font-weight: 700; }
.ghost-t { color: var(--ink-2); }
.primary-t { color: var(--on-accent); }

/* ── 页内绑定弹窗 ── */
.bind-modal-tip { display: block; font-size: 23rpx; color: var(--ink-3); margin: -12rpx 0 24rpx; line-height: 1.5; }
</style>
