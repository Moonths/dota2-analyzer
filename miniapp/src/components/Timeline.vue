<script setup>
defineProps({
  events: { type: Array, required: true },
})

function formatTime(sec) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function iconForType(t) {
  const map = { kill: 'X', tower: 'T', roshan: 'R', item: 'I', aegis: 'A' }
  return map[t] || 'O'
}
</script>

<template>
  <view class="timeline">
    <view v-for="(ev, i) in events" :key="i" :class="['tl-item', `tl-${ev.importance}`]">
      <view class="tl-dot">
        <text class="tl-icon">{{ iconForType(ev.event_type) }}</text>
      </view>
      <view class="tl-line" v-if="i < events.length - 1"></view>
      <view class="tl-content">
        <view class="tl-top">
          <text class="tl-type">{{ ev.event_type }}</text>
          <text class="tl-time">{{ formatTime(ev.time) }}</text>
        </view>
        <text class="tl-desc">{{ ev.description }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.timeline {
  display: flex;
  flex-direction: column;
}
.tl-item {
  display: flex;
  align-items: flex-start;
  position: relative;
  padding-bottom: 32rpx;
}
.tl-dot {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 22rpx;
  font-weight: 800;
  flex-shrink: 0;
  background: var(--bg-card);
  border: 2px solid var(--border);
  z-index: 1;
}
.tl-critical .tl-dot {
  border-color: var(--red);
  background: rgba(248, 81, 73, .08);
}
.tl-high .tl-dot {
  border-color: var(--orange);
  background: rgba(245, 158, 11, .08);
}
.tl-icon {
  font-size: 20rpx;
  font-weight: 800;
}
.tl-line {
  position: absolute;
  left: 23rpx;
  top: 48rpx;
  width: 2px;
  bottom: 0;
  background: var(--border);
}
.tl-content {
  flex: 1;
  margin-left: 24rpx;
  min-width: 0;
}
.tl-top {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 8rpx;
}
.tl-type {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.tl-time {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--text-muted);
}
.tl-desc {
  font-size: 26rpx;
  color: var(--text-primary);
  line-height: 1.5;
  font-weight: 500;
}
</style>
