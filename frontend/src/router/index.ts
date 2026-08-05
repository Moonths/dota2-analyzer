import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Analysis from '../views/Analysis.vue'
import Share from '../views/Share.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/analysis/:matchId', component: Analysis, props: true },
    { path: '/share/:shareId', component: Share, props: true },
  ],
})

export default router
