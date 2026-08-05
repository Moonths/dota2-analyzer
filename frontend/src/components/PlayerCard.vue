<script setup lang="ts">
import type { PlayerCard as PC } from '../api'

defineProps<{ player: PC }>()

const POS_LABELS: Record<number, string> = {
  1: '1号位 Carry', 2: '2号位 Mid', 3: '3号位 Offlane', 4: '4号位 Sup', 5: '5号位 Sup',
}
</script>

<template>
  <div class="player-card">
    <div class="card-header">
      <img :src="player.hero_icon" :alt="player.hero_name" class="hero-avatar" />
      <div class="header-info">
        <div class="player-name">{{ player.player_name }}</div>
        <div class="hero-name">{{ player.hero_name }}</div>
      </div>
      <span :class="['tag', player.is_winner ? 'tag-win' : 'tag-loss']">
        {{ player.is_winner ? 'WIN' : 'LOSS' }}
      </span>
    </div>
    <div class="card-body">
      <div class="stat">
        <span class="stat-label">KDA</span>
        <span class="stat-value">{{ player.kda }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">GPM</span>
        <span class="stat-value">{{ player.gpm }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">XPM</span>
        <span class="stat-value">{{ player.xpm }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">补刀</span>
        <span class="stat-value">{{ player.last_hits }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.player-card { background: var(--bg); border-radius: var(--r); overflow: hidden; border: 1px solid var(--border); transition: border-color var(--transition); }
.player-card:hover { border-color: var(--border-light); }
.card-header { display: flex; align-items: center; gap: 10px; padding: 12px 14px; }
.hero-avatar { width: 52px; height: 29px; border-radius: var(--r-sm); object-fit: cover; }
.header-info { flex: 1; min-width: 0; }
.player-name { font-weight: 700; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; letter-spacing: -0.01em; }
.hero-name { font-size: 11px; color: var(--ink-3); font-weight: 500; }
.card-body {
  display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--border);
}
.stat {
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 14px; background: var(--bg);
}
.stat-label { font-size: 10px; color: var(--ink-3); text-transform: uppercase; font-weight: 600; letter-spacing: 0.04em; }
.stat-value { font-size: 13px; font-weight: 700; color: var(--ink-1); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
</style>
