<template>
  <AppShell
    :route-workspace-tab="routeState.routeWorkspaceTab"
    :route-right-tab="routeState.routeRightTab"
    :route-ticker="routeState.routeTicker"
    @route-change="handleRouteChange"
  />
</template>

<script setup>
import { computed, defineAsyncComponent } from "vue";
import { useRoute, useRouter } from "vue-router";

import { buildAppRouteLocation, mapRouteToAppState } from "../router/appRouteState";

const AppShell = defineAsyncComponent(() => import("../App.vue"));

const route = useRoute();
const router = useRouter();

const routeState = computed(() => mapRouteToAppState(route));

async function handleRouteChange(payload) {
  const target = buildAppRouteLocation(payload);
  const current = buildAppRouteLocation({
    workspaceTab: routeState.value.routeWorkspaceTab,
    rightTab: routeState.value.routeRightTab,
    currentTicker: routeState.value.routeTicker,
  });
  if (
    target.name === current.name
    && String(target.params?.ticker || "") === String(current.params?.ticker || "")
  ) {
    return;
  }
  await router.replace(target);
}
</script>
