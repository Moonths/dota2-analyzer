<script>
import { onLaunch } from '@dcloudio/uni-app'
import { ensureLogin } from './utils/auth.js'
export default {
  setup() {
    onLaunch(() => { ensureLogin() })
  }
}
</script>
<template>
  <view class="app">
    <!-- pages.json already configures nav bar, no header needed in template -->
  </view>
</template>

<style>
/* global styles */
page {
  --page: #111110;
  --bg: #1a1a17;
  --panel-2: #242420;
  --border: rgba(156, 147, 132, .12);
  --border-light: rgba(156, 147, 132, .18);
  --ink-1: #ede8dc;
  --ink-2: #a09b8f;
  --ink-3: #6b675e;
  --accent: #d4a843;
  --accent-soft: rgba(212, 168, 67, .12);
  --on-accent: #1a1810;
  --up: #3fb950;
  --down: #f85149;
  --warn: #f59e0b;
  --shadow: 0 2rpx 6rpx rgba(20, 18, 10, .4);
  --r: 18rpx;
  --r-sm: 11rpx;
  --bg-primary: var(--page);
  --bg-secondary: var(--bg);
  --bg-card: var(--bg);
  --bg-card-hover: var(--panel-2);
  --text-primary: var(--ink-1);
  --text-secondary: var(--ink-2);
  --text-muted: var(--ink-3);
  --gold: var(--accent);
  --gold-400: #f0c050;
  --gold-500: var(--accent);
  --gold-600: #b8912e;
  --gold-dim: #7a601e;
  --green-400: #4ade80;
  --green: var(--up);
  --green-600: #2d9a3c;
  --red-400: #f87171;
  --red: var(--down);
  --red-600: #d93d36;
  --orange: #f59e0b;
  --blue-400: #60a5fa;
  --blue: #3b82f6;
  --purple-400: #a78bfa;
  --purple: #8b5cf6;
  --radius: var(--r);
  --radius-sm: var(--r-sm);
  --radius-lg: var(--r);
  --radius-xl: var(--r);
  --transition: 0.2s ease;
  --shadow-sm: var(--shadow);
  background: var(--page);
  color: var(--text-primary);
  font-size: 28rpx;
  line-height: 1.6;
  min-height: 100vh;
}
</style>
