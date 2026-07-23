import { createApp } from "vue";

import AppRoot from "./AppRoot.vue";
import { router } from "./router";
import {
  markQuantVisionPerformance,
  QV_PERFORMANCE_MARKS,
  startQuantVisionPerformanceObserver,
} from "./utils/performanceMarks";
import "./styles/fonts.css";
import "./styles/dashboard.css";

startQuantVisionPerformanceObserver();
createApp(AppRoot).use(router).mount("#app");
markQuantVisionPerformance(QV_PERFORMANCE_MARKS.appMounted);
