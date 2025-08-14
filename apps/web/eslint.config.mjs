import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";
import eslintConfigPrettier from "eslint-config-prettier";
import noAdminClientFetch from "./eslint/no-admin-client-fetch.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  {
    ignores: ["**/.next/**"],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  eslintConfigPrettier,
  {
    plugins: {
      internal: {
        rules: {
          "no-admin-client-fetch": noAdminClientFetch,
        },
      },
    },
    rules: {
      "internal/no-admin-client-fetch": "error",
    },
  },
];

export default eslintConfig;
