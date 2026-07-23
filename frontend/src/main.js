import { createApp } from "vue";

import AppRoot from "./AppRoot.vue";
import { router } from "./router";
import { markQuantVisionPerformance, QV_PERFORMANCE_MARKS } from "./utils/performanceMarks";
import "./styles/dashboard.css";

createApp(AppRoot).use(router).mount("#app");
markQuantVisionPerformance(QV_PERFORMANCE_MARKS.appMounted);
