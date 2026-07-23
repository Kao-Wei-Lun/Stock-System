import { createApp } from "vue";

import AppRoot from "./AppRoot.vue";
import { router } from "./router";
import {
  markQuantVisionPerformance,
  QV_PERFORMANCE_MARKS,
  startQuantVisionPerformanceObserver,
} from "./utils/performanceMarks";
import { installUnhandledRejectionReporter } from "./utils/frontendRecovery";
import "./styles/fonts.css";
import "./styles/dashboard.css";

startQuantVisionPerformanceObserver();
installUnhandledRejectionReporter();
createApp(AppRoot).use(router).mount("#app");
markQuantVisionPerformance(QV_PERFORMANCE_MARKS.appMounted);
