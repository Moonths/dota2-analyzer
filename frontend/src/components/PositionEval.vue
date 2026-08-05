<script setup lang="ts">
import type { PositionEval as PE, PlayerCard } from '../api'

const props = defineProps<{ eval: PE; playerCard?: PlayerCard }>()

function scoreColor(s: number): string {
  if (s >= 75) return 'var(--green)'
  if (s >= 50) return 'var(--orange)'
  return 'var(--red)'
}
function formatStat(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}
</script>

<template>
  <div :class="['eval-card', { qualified: eval.is_qualified, 'not-qualified': !eval.is_qualified }]">
    <div class="eval-header">
      <div class="eval-hero" v-if="playerCard">
        <img :src="playerCard.hero_icon" class="hero-icon" />
        <div class="hero-info">
          <span class="pos-badge">{{ eval.position }}号位</span>
          <span class="player-name">{{ eval.player_name }}</span>
        </div>
      </div>
      <div class="eval-stats" v-if="playerCard">
        <span class="stat-item"><span class="stat-val">{{ playerCard.kda }}</span><span class="stat-lbl">KDA</span></span>
        <span class="stat-item"><span class="stat-val">{{ playerCard.gpm }}</span><span class="stat-lbl">GPM</span></span>
        <span class="stat-item"><span class="stat-val">{{ playerCard.xpm }}</span><span class="stat-lbl">XPM</span></span>
        <span class="stat-item"><span class="stat-val">{{ formatStat(playerCard.hero_damage) }}</span><span class="stat-lbl">伤害</span></span>
      </div>
      <div class="eval-score" :style="{ color: scoreColor(eval.score) }">{{ eval.score }}</div>
      <span :class="['tag', eval.is_qualified ? 'tag-win' : 'tag-loss']">{{ eval.is_qualified ? 'PASS' : 'FAIL' }}</span>
    </div>
    <p class="eval-summary">{{ eval.summary }}</p>
    <div class="eval-details">
      <div v-if="eval.highlights.length" class="eval-section">
        <div class="eval-label">亮点</div>
        <ul><li v-for="h in eval.highlights" :key="h">✦ {{ h }}</li></ul>
      </div>
      <div v-if="eval.improvements.length" class="eval-section">
        <div class="eval-label">改进建议</div>
        <ul><li v-for="imp in eval.improvements" :key="imp">→ {{ imp }}</li></ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.eval-card {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--r); padding: 20px;
  transition: border-color var(--transition), background var(--transition);
}
.eval-card.qualified { background: rgba(63,185,80,.03); border-color: rgba(63,185,80,.15); }
.eval-card.not-qualified { background: rgba(248,81,73,.03); border-color: rgba(248,81,73,.15); }
.eval-card:hover { border-color: var(--border-light); }
.eval-header { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.eval-hero { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1; }
.hero-icon {
  width: 52px; height: 29px; border-radius: var(--r-sm); object-fit: cover;
  flex-shrink: 0;
}
.hero-info { display: flex; flex-direction: column; gap: 2px; }
.pos-badge {
  font-size: 10px; font-weight: 700; color: var(--gold-400);
  text-transform: uppercase; letter-spacing: 0.08em;
}
.player-name { font-size: 14px; font-weight: 600; color: var(--ink-1); white-space: nowrap; }
.eval-stats { display: flex; gap: 20px; flex: 1; justify-content: center; }
.stat-item { display: flex; flex-direction: column; align-items: center; gap: 1px; }
.stat-val { font-size: 14px; font-weight: 700; color: var(--text-primary); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
.stat-lbl { font-size: 9px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.eval-score {
  font-size: 32px; font-weight: 900; min-width: 52px; text-align: center;
  flex-shrink: 0; letter-spacing: -0.02em; line-height: 1;
}
.eval-summary {
  font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;
  line-height: 1.6; padding-left: 62px;
}
.eval-details { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding-left: 62px; }
@media (max-width: 500px) { .eval-details { grid-template-columns: 1fr; } }
.eval-label { font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.06em; }
.eval-section ul { list-style: none; padding: 0; }
.eval-section li {
  font-size: 12px; color: var(--text-secondary); padding: 3px 0; line-height: 1.5;
}
.eval-section li { padding: 3px 0; line-height: 1.5; }
@media (max-width: 480px) {
  .eval-card { padding: 14px; }
  .eval-header { flex-wrap: wrap; }
  .eval-stats { flex: 1 1 100%; justify-content: flex-start; gap: 12px; padding-left: 62px; }
  .eval-score { position: absolute; top: 14px; right: 14px; }
  .eval-summary { padding-left: 0; }
  .eval-details { padding-left: 0; }
}
</style>
