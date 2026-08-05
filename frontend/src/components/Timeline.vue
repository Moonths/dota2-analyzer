<script setup lang="ts">
import type { TimelineEvent } from '../api'
defineProps<{ events: TimelineEvent[] }>()
function formatTime(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}
function iconForType(t: string): string {
  const map: Record<string, string> = { kill: '\u2694', tower: '\u{1F3F0}', roshan: '\u{1F525}', item: '\u{1F392}', aegis: '\u{1F451}' }
  return map[t] || '\u25CF'
}
</script>

<template>
  <div class="timeline">
    <div v-for="(ev, i) in events" :key="i" :class="['tl-item', `tl-${ev.importance}`]">
      <div class="tl-time">{{ formatTime(ev.time) }}</div>
      <div class="tl-dot">{{ iconForType(ev.event_type) }}</div>
      <div class="tl-content">
        <div class="tl-type">{{ ev.event_type }}</div>
        <p class="tl-desc">{{ ev.description }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline { position: relative; padding-left: 80px; }
.tl-item { display: flex; align-items: flex-start; gap: 12px; padding: 8px 0; position: relative; }
.tl-item::before { content: ''; position: absolute; left: -38px; top: 24px; width: 2px; height: calc(100% + 8px); background: var(--border); }
.tl-item:last-child::before { display: none; }
.tl-time { position: absolute; left: -80px; font-size: 12px; font-weight: 700; color: var(--text-muted); font-variant-numeric: tabular-nums; width: 60px; text-align: right; }
.tl-dot { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 13px; flex-shrink: 0; background: var(--bg-card); border: 2px solid var(--border); position: relative; z-index: 1; }
.tl-critical .tl-dot { border-color: var(--red); background: rgba(248,81,73,0.08); box-shadow: 0 0 8px rgba(248,81,73,0.15); }
.tl-high .tl-dot { border-color: var(--orange); background: rgba(245,158,11,0.08); }
.tl-content { flex: 1; }
.tl-type { font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 2px; }
.tl-desc { font-size: 13px; color: var(--text-primary); line-height: 1.5; font-weight: 500; }
@media (max-width: 480px) {
  .timeline { padding-left: 60px; }
  .tl-time { left: -60px; width: 50px; font-size: 11px; }
  .tl-item::before { left: -30px; }
  .tl-dot { width: 20px; height: 20px; font-size: 11px; }
}
</style>
