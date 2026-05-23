<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink to="/" class="app-brand">AI Trend Studio</RouterLink>
      <nav class="app-nav" aria-label="主导航">
        <RouterLink to="/">热词洞察</RouterLink>
        <RouterLink to="/digital-human-video">数字人视频</RouterLink>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
