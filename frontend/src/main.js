import { createApp } from "vue";

import AppRoot from "./AppRoot.vue";
import { router } from "./router";
import "./styles/dashboard.css";

createApp(AppRoot).use(router).mount("#app");
