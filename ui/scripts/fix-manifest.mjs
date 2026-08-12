import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = resolve(root, "dist/.vite/manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));

if (manifest["src/index.tsx"] && !manifest["index.tsx"]) {
  manifest["index.tsx"] = manifest["src/index.tsx"];
  delete manifest["src/index.tsx"];
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}
