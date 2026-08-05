<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app">
    <header class="app-header">
      <div class="container header-inner">
        <router-link to="/" class="logo">
          <span class="logo-icon">◈</span>
          <span class="logo-text">Dota 2 AI 赛后复盘</span>
        </router-link>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-header {
  background: rgba(26,26,23,.88);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  display: flex;
  align-items: center;
  height: 56px;
}
.logo {
  display: flex; align-items: center; gap: 10px;
  color: var(--ink-1); font-weight: 800; font-size: 15px; letter-spacing: -0.01em;
}
.logo:hover { text-decoration: none; }
.logo-icon {
  display: flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: var(--r-sm);
  background: var(--accent); color: var(--on-accent);
  font-size: 16px; font-weight: 900;
}
.app-main { min-height: calc(100vh - 56px); }
</style>
