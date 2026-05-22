import { createRouter, createWebHistory } from "vue-router";
import HotwordsList from "./pages/HotwordsList.vue";
import HotwordDetail from "./pages/HotwordDetail.vue";
import { fetchSessionInfo } from "./api/client";

async function requireAdmin() {
  const session = await fetchSessionInfo();
  return session?.is_admin ? true : "/";
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: HotwordsList, props: { mode: "public" } },
    { path: "/manage", component: HotwordsList, props: { mode: "admin" }, beforeEnter: requireAdmin },
    { path: "/hotwords/:id", component: HotwordDetail },
  ],
});

export default router;
