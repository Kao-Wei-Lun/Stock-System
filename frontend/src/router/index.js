import { createRouter, createWebHistory } from "vue-router";

const DashboardView = () => import("../views/DashboardView.vue");
const AlertsView = () => import("../views/AlertsView.vue");
const BacktestView = () => import("../views/BacktestView.vue");
const JournalView = () => import("../views/JournalView.vue");
const DatabaseView = () => import("../views/DatabaseView.vue");
const InstitutionalView = () => import("../views/InstitutionalView.vue");
const EventsView = () => import("../views/EventsView.vue");
const MacroView = () => import("../views/MacroView.vue");
const ScreenerView = () => import("../views/ScreenerView.vue");

const routes = [
  {
    path: "/",
    redirect: { name: "dashboard" },
  },
  {
    path: "/dashboard/:ticker?",
    name: "dashboard",
    component: DashboardView,
  },
  {
    path: "/alerts/:ticker?",
    name: "alerts",
    component: AlertsView,
  },
  {
    path: "/backtest/:ticker?",
    name: "backtest",
    component: BacktestView,
  },
  {
    path: "/journal/:ticker?",
    name: "journal",
    component: JournalView,
  },
  {
    path: "/db/:ticker?",
    name: "db",
    component: DatabaseView,
  },
  {
    path: "/institutional/:ticker?",
    name: "institutional",
    component: InstitutionalView,
  },
  {
    path: "/events/:ticker?",
    name: "events",
    component: EventsView,
  },
  {
    path: "/macro/:ticker?",
    name: "macro",
    component: MacroView,
  },
  {
    path: "/screener/:ticker?",
    name: "screener",
    component: ScreenerView,
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});
