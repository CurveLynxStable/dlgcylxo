import tailwindcss from "@tailwindcss/vite";
// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  appDir: "app",
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: ["@nuxt/eslint"],
  components: {
    dirs: [{ path: "~/components", pathPrefix: false }],
  },
  // SSR отключён, так как Tauri его не поддерживает
  ssr: false,
  // Делает dev-сервер видимым для других устройств, чтобы запускать на физическом iOS-устройстве.
  devServer: { host: process.env.TAURI_DEV_HOST || "localhost" },
  vite: {
    // Лучшая поддержка вывода команд Tauri
    clearScreen: false,
    // Включение переменных окружения
    // Прочие переменные окружения см. на странице:
    // https://v2.tauri.app/reference/environment-variables/
    envPrefix: ["VITE_", "TAURI_"],
    server: {
      // Tauri требуется фиксированный порт
      strictPort: true,
      // В разработке кэш отключён, чтобы Tauri WebView не читал повреждённый кэш
      headers: {
        "Cache-Control": "no-store",
        Pragma: "no-cache",
        Expires: "0",
      },
    },
    plugins: [tailwindcss()],
  },
  css: ["~/assets/css/tailwind.css"],
  ignore: ["**/src-tauri/**"],
});
