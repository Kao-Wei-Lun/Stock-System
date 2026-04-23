<template>
  <div class="paper-trading-page">
    <PaperTradingDashboard />
  </div>
</template>

<script setup>
import PaperTradingDashboard from "../components/PaperTradingDashboard.vue";
</script>

<style scoped>
.paper-trading-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #080c13 0%, #0d1520 50%, #0a1018 100%);
  color: #e6f1ff;
}
</style>
