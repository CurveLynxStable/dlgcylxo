import withNuxt from "./.nuxt/eslint.config.mjs";
import betterTailwind from "eslint-plugin-better-tailwindcss";
import eslintConfigPrettier from "eslint-config-prettier/flat";
import eslintPluginPrettier from "eslint-plugin-prettier";
import * as yamlParser from "yaml-eslint-parser";
import * as eslintPluginYml from "eslint-plugin-yml";

export default withNuxt(
  {
    ignores: [
      "node_modules",
      ".nuxt",
      ".output",
      "dist",
      "src-tauri",
      "python-src",
      "pnpm-lock.yaml",
    ],
  },
  {
    files: ["**/*.{ts,tsx,vue}"],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: process.cwd(),
      },
    },
    rules: {
      "@typescript-eslint/no-unsafe-type-assertion": "warn",
      "@typescript-eslint/no-unnecessary-type-assertion": "warn",
    },
  },
  // Prettier как источник диагностик ESLint (панель Problems показывает конкретные расхождения в реальном времени)
  {
    files: ["**/*.{js,mjs,cjs,ts,tsx,vue}"],
    plugins: {
      prettier: eslintPluginPrettier,
    },
    rules: {
      "prettier/prettier": "warn",
    },
  },
  // Поддержка YAML
  {
    files: ["**/*.{yaml,yml}"],
    languageOptions: {
      parser: yamlParser,
    },
    plugins: {
      yml: eslintPluginYml.default || eslintPluginYml,
    },
    rules: {
      // Соответствует document-start: present: false
      "yml/file-header": "off",

      // Соответствует indentation: spaces: 2, indent-sequences: true
      "yml/indent": ["error", 2, { indentBlockSequences: true }],

      // У YAML-плагина нет line-length; используем общее правило ESLint или отключаем
      "max-len": ["warn", { code: 175, ignoreUrls: true }],

      // Соответствует trailing-spaces: level: warning
      "no-trailing-spaces": "warn",

      // Соответствует comments: min-spaces-from-content: 1
      "yml/spaced-comment": ["error", "always"],
    },
  },
  // Поддержка Better Tailwind CSS
  {
    plugins: {
      "better-tailwindcss": betterTailwind,
    },
    rules: {
      // Уровень warn вместо error, чтобы не блокировать разработку
      ...Object.fromEntries(
        Object.entries(betterTailwind.configs.recommended.rules).map(([key, value]) => [
          key,
          value === "error" ? "warn" : value,
        ]),
      ),
      "better-tailwindcss/no-unregistered-classes": "off", // Классы daisyUI часто считаются незарегистрированными — временно отключено
      "better-tailwindcss/enforce-consistent-class-order": "off", // Правило сортировки слишком строгое — временно отключено
      "better-tailwindcss/enforce-consistent-line-wrapping": "off", // Правило переносов слишком строгое — временно отключено
      "vue/multi-word-component-names": "off", // Разрешить однословные имена компонентов
      "vue/html-self-closing": "off", // Разрешить самозакрывающиеся теги для HTML void elements
      "@typescript-eslint/unified-signatures": "off", // Разрешить раздельное определение перегрузок (часто в defineEmits)
    },
    settings: {
      "better-tailwindcss": {
        // CSS-входной файл Tailwind v4
        entryPoint: "app/assets/css/tailwind.css",
      },
    },
  },
  // Отключить правила ESLint, конфликтующие с Prettier
  eslintConfigPrettier,
);
