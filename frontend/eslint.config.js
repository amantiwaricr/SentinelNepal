import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig([
  globalIgnores(['dist', 'coverage']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    rules: {
      // AGENTS.md: rendering raw HTML is forbidden (XSS risk).
      'no-restricted-syntax': [
        'error',
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: 'dangerouslySetInnerHTML is not allowed in SentinelNepal (XSS risk).',
        },
      ],
      // AGENTS.md: tokens must never be stored in web storage.
      'no-restricted-globals': [
        'error',
        { name: 'localStorage', message: 'Do not store data in localStorage (see AGENTS.md).' },
        { name: 'sessionStorage', message: 'Do not store data in sessionStorage (see AGENTS.md).' },
      ],
    },
  },
])
