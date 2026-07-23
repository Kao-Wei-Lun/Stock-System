<template>
  <FrontendErrorBoundary>
    <RouterView v-slot="{ Component }">
      <Suspense :timeout="0">
        <component :is="Component" />
        <template #fallback>
          <main class="route-skeleton" aria-busy="true" aria-label="頁面載入中">
            <div class="route-skeleton__nav"></div>
            <div class="route-skeleton__toolbar"></div>
            <div class="route-skeleton__workspace"></div>
          </main>
        </template>
      </Suspense>
    </RouterView>
  </FrontendErrorBoundary>
</template>

<script setup>
import { RouterView } from "vue-router";
import FrontendErrorBoundary from "./components/FrontendErrorBoundary.vue";
</script>

<style scoped>
.route-skeleton {
  min-height: 100vh;
  padding: 16px;
  background: #07101c;
}

.route-skeleton > div {
  border: 1px solid rgba(103, 205, 255, 0.08);
  border-radius: 12px;
  background: linear-gradient(90deg, #0b1726 25%, #11263c 50%, #0b1726 75%);
  background-size: 220% 100%;
  animation: route-skeleton-pulse 1.4s ease-in-out infinite;
}

.route-skeleton__nav {
  height: 72px;
}

.route-skeleton__toolbar {
  height: 48px;
  margin-top: 12px;
}

.route-skeleton__workspace {
  height: calc(100vh - 176px);
  min-height: 420px;
  margin-top: 12px;
}

@keyframes route-skeleton-pulse {
  to { background-position: -220% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .route-skeleton > div { animation: none; }
}
</style>
