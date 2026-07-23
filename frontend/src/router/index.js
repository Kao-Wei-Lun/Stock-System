import { defineAsyncComponent } from "vue";
import { createRouter, createWebHistory } from "vue-router";

import { reportFrontendError } from "../utils/frontendRecovery";

function recoverableRoute(loader) {
  return defineAsyncComponent({
    loader,
    delay: 0,
    timeout: 20_000,
    suspensible: true,
    onError(error, retry, fail, attempts) {
      if (attempts < 2) retry();
      else {
        reportFrontendError(error, "route-module");
        fail();
      }
    },
  });
}

const OverviewView = recoverableRoute(() => import("../views/OverviewView.vue"));
const TerminalView = recoverableRoute(() => import("../views/TerminalView.vue"));
const InstitutionalView = recoverableRoute(() => import("../views/InstitutionalView.vue"));
const JournalView = recoverableRoute(() => import("../views/JournalView.vue"));
const BacktestView = recoverableRoute(() => import("../views/BacktestView.vue"));
const AssetsView = recoverableRoute(() => import("../views/AssetsView.vue"));
const SettingsView = recoverableRoute(() => import("../views/SettingsView.vue"));
const PaperTradingView = recoverableRoute(() => import("../views/PaperTradingView.vue"));

const redirectWithTicker = (name) => (to) => ({
  name,
  params: to.params?.ticker ? { ticker: String(to.params.ticker) } : {},
});

const routes = [
  {
    path: "/",
    redirect: { name: "overview" },
  },
  {
    path: "/overview/:ticker?",
    name: "overview",
    component: OverviewView,
  },
  {
    path: "/terminal/:ticker?",
    name: "terminal",
    component: TerminalView,
  },
  {
    path: "/institutional/:ticker?",
    name: "institutional",
    component: InstitutionalView,
  },
  {
    path: "/review/journal/:ticker?",
    name: "journal",
    component: JournalView,
  },
  {
    path: "/review/backtest/:ticker?",
    name: "backtest",
    component: BacktestView,
  },
  {
    path: "/assets/:ticker?",
    name: "assets",
    component: AssetsView,
  },
  {
    path: "/review/assets/:ticker?",
    redirect: redirectWithTicker("assets"),
  },
  {
    path: "/settings/:ticker?",
    name: "settings",
    component: SettingsView,
  },
  {
    path: "/paper-trading",
    name: "paper-trading",
    component: PaperTradingView,
  },
  {
    path: "/dashboard/:ticker?",
    redirect: redirectWithTicker("terminal"),
  },
  {
    path: "/alerts/:ticker?",
    redirect: redirectWithTicker("terminal"),
  },
  {
    path: "/events/:ticker?",
    redirect: redirectWithTicker("overview"),
  },
  {
    path: "/macro/:ticker?",
    redirect: redirectWithTicker("overview"),
  },
  {
    path: "/screener/:ticker?",
    redirect: redirectWithTicker("overview"),
  },
  {
    path: "/db/:ticker?",
    redirect: redirectWithTicker("overview"),
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});
