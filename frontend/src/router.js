import { createRouter, createWebHistory } from "vue-router";
import HotwordsList from "./pages/HotwordsList.vue";
import HotwordDetail from "./pages/HotwordDetail.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: HotwordsList },
    { path: "/hotwords/:id", component: HotwordDetail },
  ],
});

export default router;
