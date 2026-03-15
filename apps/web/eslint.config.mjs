import eslintConfigPrettier from "eslint-config-prettier";
import noAdminClientFetch from "./eslint/no-admin-client-fetch.js";

const eslintConfig = [
  {
    ignores: ["dist/**", "coverage/**"],
  },
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
