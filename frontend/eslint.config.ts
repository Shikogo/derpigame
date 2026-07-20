import js from '@eslint/js'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import configPrettier from 'eslint-config-prettier'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default defineConfigWithVueTs(
  { ignores: ['dist/**', 'dist-local/**', 'coverage/**'] },
  js.configs.recommended,
  // `essential`, not `recommended`: the higher tiers are mostly formatting rules
  // (attribute-per-line, tag newlines) that would fight hand-written markup.
  // This project lints for correctness and leaves layout alone.
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  {
    languageOptions: { globals: globals.browser },
    rules: {
      // An unused argument is often a deliberate signature placeholder (the
      // reducer's exhaustiveness guard, event handlers); leading _ opts out.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // Guards against shadowing a real HTML element; our names don't collide.
      'vue/multi-word-component-names': 'off',
    },
  },
  // Last: drops any rule that would argue with Prettier. ESLint owns
  // correctness, Prettier owns layout — they never both have an opinion.
  configPrettier,
)
