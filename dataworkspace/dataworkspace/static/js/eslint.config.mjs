import react from 'eslint-plugin-react';
import typescriptEslint from '@typescript-eslint/eslint-plugin';
import simpleImportSort from 'eslint-plugin-simple-import-sort';
import jsxA11Y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import prettier from 'eslint-plugin-prettier';
import { fixupPluginRules } from '@eslint/compat';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import js from '@eslint/js';
import { FlatCompat } from '@eslint/eslintrc';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all
});

export default [
  {
    ignores: [
      '**/node_modules',
      'src/your-files',
      'eslint.config.mjs',
      'jest-setup.js',
      'grid-utils.js',
      'enhanced-table.js',
      'link-text-editor.js'
    ]
  },
  ...compat.extends(
    'eslint:recommended',
    'plugin:@typescript-eslint/eslint-recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:jsx-a11y/recommended',
    'prettier'
  ),
  {
    files: ['**/*.{js,jsx,ts,tsx}'], // apply these settings to source files
    plugins: {
      react,
      '@typescript-eslint': typescriptEslint,
      'simple-import-sort': simpleImportSort,
      'jsx-a11y': jsxA11Y,
      'react-hooks': fixupPluginRules(reactHooks),
      prettier
    },
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.jest,
        ...globals.node,
        // Cypress
        Cypress: 'readonly',
        cy: 'readonly',
        context: 'readonly',
        before: 'readonly',
        after: 'readonly'
      },
      parser: tsParser,
      ecmaVersion: 5,
      sourceType: 'commonjs',
      parserOptions: {
        warnOnUnsupportedTypeScriptVersion: false
      }
    },
    rules: {
      'prettier/prettier': 2,
      semi: ['error', 'always'],
      quotes: ['error', 'single', { avoidEscape: true }],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'off',
      'no-multiple-empty-lines': ['error', { max: 1 }],
      'no-undef': 'error',
      'no-console': ['error', { allow: ['assert', 'info'] }],
      'simple-import-sort/imports': [
        'error',
        {
          groups: [['^react'], ['^antd'], ['^@?\\w'], ['@/(.*)'], ['^[./]']]
        }
      ],
      '@typescript-eslint/ban-ts-comment': 'off',
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: 'govuk-react',
              importNames: ['WarningText'],
              message:
                "Do not import 'WarningText' from 'govuk-react'. Use '../components/WarningText' instead."
            }
          ]
        }
      ]
    }
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      globals: {
        JQuery: 'readonly'
      }
    }
  }
];
