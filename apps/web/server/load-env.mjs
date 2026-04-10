import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../../..");

function parseEnvFile(filePath) {
  const entries = readFileSync(filePath, "utf8").split(/\r?\n/);
  for (const line of entries) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const separator = trimmed.indexOf("=");
    if (separator <= 0) {
      continue;
    }
    const key = trimmed.slice(0, separator).trim();
    const rawValue = trimmed.slice(separator + 1).trim();
    const quoted =
      (rawValue.startsWith('"') && rawValue.endsWith('"')) ||
      (rawValue.startsWith("'") && rawValue.endsWith("'"));
    const value = quoted ? rawValue.slice(1, -1) : rawValue;
    if (!(key in process.env)) {
      process.env[key] = value;
    }
  }
}

export function loadAppEnv() {
  for (const relativePath of [".env", ".env.local"]) {
    const filePath = path.join(repoRoot, relativePath);
    if (existsSync(filePath)) {
      parseEnvFile(filePath);
    }
  }
}
