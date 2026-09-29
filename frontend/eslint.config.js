// Purpose: focused correctness checks for the active dashboard code.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
export default [
  { ignores: ["dist/**"] },
  js.configs.recommended,
  { files: ["src/**/*.{js,jsx}"], languageOptions: { globals: globals.browser, parserOptions: { ecmaFeatures: { jsx: true } } },
    plugins: { "react-hooks": reactHooks },
    rules: { ...reactHooks.configs.recommended.rules, "no-unused-vars": ["error", { varsIgnorePattern: "^[A-Z]", argsIgnorePattern: "^_" }] } },
  { files: ["*.config.js"], languageOptions: { globals: globals.node } },
];
