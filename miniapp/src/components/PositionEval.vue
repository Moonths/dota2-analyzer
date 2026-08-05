<script setup>
import { heroImg } from '../utils/image.js'


defineProps({
  eval: { type: Object, required: true },
  playerCard: { type: Object, default: null },
})

function scoreColor(s) {
  if (s >= 75) return 'var(--green)'
  if (s >= 50) return 'var(--orange)'
  return 'var(--red)'
}

function formatStat(n) {
  if (!n) return '0'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}
</script>

<template>
  <view :class="['eval-card', { qualified: eval.is_qualified, 'not-qualified': !eval.is_qualified }]">
    <!-- Row 1: hero + name/pos + score + tag -->
    <view class="eval-top">
      <view class="eval-hero" v-if="playerCard">
        <image :src="heroImg(playerCard.hero_icon)" mode="aspectFill" class="hero-icon" />
        <view class="hero-info">
          <text class="pos-badge">{{ eval.position }}号位</text>
          <text class="player-name">{{ eval.player_name }}</text>
        </view>
      </view>
      <text class="eval-score" :style="{ color: scoreColor(eval.score) }">{{ eval.score }}</text>
      <text :class="['tag', eval.is_qualified ? 'tag-win' : 'tag-loss']">{{ eval.is_qualified ? 'PASS' : 'FAIL' }}</text>
    </view>

    <!-- Row 2: stats bar -->
    <view class="eval-stats" v-if="playerCard">
      <view class="stat-item">
        <text class="stat-val">{{ playerCard.kda }}</text>
        <text class="stat-lbl">KDA</text>
      </view>
      <view class="stat-item">
        <text class="stat-val">{{ playerCard.gpm }}</text>
        <text class="stat-lbl">GPM</text>
      </view>
      <view class="stat-item">
        <text class="stat-val">{{ playerCard.xpm }}</text>
        <text class="stat-lbl">XPM</text>
      </view>
      <view class="stat-item">
        <text class="stat-val">{{ formatStat(playerCard.hero_damage) }}</text>
        <text class="stat-lbl">伤害</text>
      </view>
    </view>

    <text class="eval-summary">{{ eval.summary }}</text>
    <view class="eval-details">
      <view v-if="eval.highlights && eval.highlights.length" class="eval-section">
        <text class="eval-label">亮点</text>
        <view v-for="(h, i) in eval.highlights" :key="i" class="eval-item">
          <text class="eval-bullet">+</text>
          <text>{{ h }}</text>
        </view>
      </view>
      <view v-if="eval.improvements && eval.improvements.length" class="eval-section">
        <text class="eval-label">改进建议</text>
        <view v-for="(imp, i) in eval.improvements" :key="i" class="eval-item">
          <text class="eval-bullet imp">-</text>
          <text>{{ imp }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.eval-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 32rpx;
}
.eval-card.qualified {
  background: rgba(63, 185, 80, .03);
  border-color: rgba(63, 185, 80, .15);
}
.eval-card.not-qualified {
  background: rgba(248, 81, 73, .03);
  border-color: rgba(248, 81, 73, .15);
}

/* Row 1: hero icon + name/pos + score + tag */
.eval-top {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
}
.eval-hero {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}
.hero-icon {
  width: 80rpx;
  height: 44rpx;
  border-radius: var(--r-sm);
  flex-shrink: 0;
}
.hero-info {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
  min-width: 0;
}
.pos-badge {
  font-size: 18rpx;
  font-weight: 700;
  color: var(--gold-400);
  letter-spacing: 0.08em;
}
.player-name {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--ink-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.eval-score {
  font-size: 52rpx;
  font-weight: 900;
  text-align: center;
  flex-shrink: 0;
  letter-spacing: -0.02em;
  line-height: 1;
}

/* Row 2: stats bar */
.eval-stats {
  display: flex;
  justify-content: space-around;
  padding: 16rpx 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  margin-bottom: 20rpx;
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rpx;
}
.stat-val {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--text-primary);
}
.stat-lbl {
  font-size: 16rpx;
  font-weight: 600;
  color: var(--text-muted);
}

.eval-summary {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 20rpx;
  line-height: 1.6;
  display: block;
}
.eval-details {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.eval-label {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 10rpx;
  letter-spacing: 0.06em;
}
.eval-item {
  display: flex;
  gap: 10rpx;
  padding: 4rpx 0;
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.5;
}
.eval-bullet {
  color: var(--green-400);
  flex-shrink: 0;
  font-weight: 700;
}
.eval-bullet.imp {
  color: var(--orange);
}

.tag {
  display: inline-flex;
  align-items: center;
  padding: 6rpx 18rpx;
  border-radius: 20rpx;
  font-size: 22rpx;
  font-weight: 800;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}
.tag-win {
  background: rgba(63, 185, 80, .15);
  color: var(--green-400);
  border: 1px solid rgba(63, 185, 80, .25);
}
.tag-loss {
  background: rgba(248, 81, 73, .12);
  color: var(--red-400);
  border: 1px solid rgba(248, 81, 73, .22);
}
.tag-win {
  background: rgba(63, 185, 80, .1);
  color: var(--green-400);
}
.tag-loss {
  background: rgba(248, 81, 73, .1);
  color: var(--red-400);
}
</style>
