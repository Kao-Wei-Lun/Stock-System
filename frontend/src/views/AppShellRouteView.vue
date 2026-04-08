<template>
  <AppShell
    :route-workspace-tab="workspaceTab"
    :route-right-tab="rightTab"
    :route-ticker="routeTicker"
    @route-change="handleRouteChange"
  />
</template>

<script setup>
import { computed, defineAsyncComponent } from "vue";
import { useRoute, useRouter } from "vue-router";

import { buildAppRouteLocation } from "../router/appRouteState";

const props = defineProps({
  workspaceTab: { type: String, default: "overview" },
  rightTab: { type: String, default: "indicators" },
});

const AppShell = defineAsyncComponent(() => import("../App.vue"));

const route = useRoute();
const router = useRouter();

const routeTicker = computed(() => String(route.params?.ticker || "").trim().toUpperCase());

async function handleRouteChange(payload) {
  const target = buildAppRouteLocation(payload);
  if (
    target.name === route.name
    && String(target.params?.ticker || "") === routeTicker.value
  ) {
    return;
  }
  await router.replace(target);
}
</script>
