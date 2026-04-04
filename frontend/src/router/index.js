import { createRouter, createWebHistory } from "vue-router";

const AppRoutePage = () => import("../pages/AppRoutePage.vue");

const routes = [
  {
    path: "/",
    redirect: { name: "dashboard" },
  },
  {
    path: "/dashboard/:ticker?",
    name: "dashboard",
    component: AppRoutePage,
  },
  {
    path: "/alerts/:ticker?",
    name: "alerts",
    component: AppRoutePage,
  },
  {
    path: "/backtest/:ticker?",
    name: "backtest",
    component: AppRoutePage,
  },
  {
    path: "/journal/:ticker?",
    name: "journal",
    component: AppRoutePage,
  },
  {
    path: "/db/:ticker?",
    name: "db",
    component: AppRoutePage,
  },
  {
    path: "/institutional/:ticker?",
    name: "institutional",
    component: AppRoutePage,
  },
  {
    path: "/events/:ticker?",
    name: "events",
    component: AppRoutePage,
  },
  {
    path: "/macro/:ticker?",
    name: "macro",
    component: AppRoutePage,
  },
  {
    path: "/screener/:ticker?",
    name: "screener",
    component: AppRoutePage,
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});
