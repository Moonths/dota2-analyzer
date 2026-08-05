<script setup>
defineProps({
  player: { type: Object, required: true },
})
</script>

<template>
  <view class="player-card">
    <view class="card-header">
      <image :src="player.hero_icon" mode="aspectFill" class="hero-avatar" />
      <view class="header-info">
        <text class="player-name">{{ player.player_name }}</text>
        <text class="hero-name">{{ player.hero_name }}</text>
      </view>
      <text :class="['tag', player.is_winner ? 'tag-win' : 'tag-loss']">
        {{ player.is_winner ? 'WIN' : 'LOSS' }}
      </text>
    </view>
    <view class="card-body">
      <view class="stat">
        <text class="stat-label">KDA</text>
        <text class="stat-value">{{ player.kda }}</text>
      </view>
      <view class="stat">
        <text class="stat-label">GPM</text>
        <text class="stat-value">{{ player.gpm }}</text>
      </view>
      <view class="stat">
        <text class="stat-label">XPM</text>
        <text class="stat-value">{{ player.xpm }}</text>
      </view>
      <view class="stat">
        <text class="stat-label">补刀</text>
        <text class="stat-value">{{ player.last_hits }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.player-card {
  background: var(--bg);
  border-radius: var(--r);
  overflow: hidden;
  border: 1px solid var(--border);
}
.card-header {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 28rpx 28rpx;
}
.hero-avatar {
  width: 96rpx;
  height: 54rpx;
  border-radius: var(--r-sm);
  flex-shrink: 0;
}
.header-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.player-name {
  font-weight: 700;
  font-size: 28rpx;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}
.hero-name {
  font-size: 22rpx;
  color: var(--ink-3);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}
.card-body {
  display: flex;
  flex-wrap: wrap;
}
.stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14rpx 28rpx;
  background: var(--bg);
  width: 50%;
  box-sizing: border-box;
  border-top: 1px solid var(--border);
}
.stat:nth-child(odd) {
  border-right: 1px solid var(--border);
}
.stat-label {
  font-size: 20rpx;
  color: var(--ink-3);
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.stat-value {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--ink-1);
}
.tag {
  display: inline-flex;
  align-items: center;
  padding: 4rpx 16rpx;
  border-radius: var(--r-sm);
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 0.03em;
  flex-shrink: 0;
}
.tag-win { background: rgba(63, 185, 80, .1); color: var(--green-400); }
.tag-loss { background: rgba(248, 81, 73, .1); color: var(--red-400); }
</style>
