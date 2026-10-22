import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const specPath = path.resolve(repoRoot, "docs/openapi.json");
const currentTypesPath = path.resolve(__dirname, "../src/lib/api-types.ts");

if (!fs.existsSync(specPath)) {
  console.error(`Error: OpenAPI specification not found at ${specPath}`);
  process.exit(1);
}

if (!fs.existsSync(currentTypesPath)) {
  console.error(`Error: Generated API types file not found at ${currentTypesPath}`);
  process.exit(1);
}

const currentContent = fs.readFileSync(currentTypesPath, "utf-8").replace(/\r\n/g, "\n");

try {
  const generatedContent = execSync(
    `npx openapi-typescript "${specPath}"`,
    { encoding: "utf-8", maxBuffer: 10 * 1024 * 1024 }
  ).replace(/\r\n/g, "\n");

  if (currentContent.trim() !== generatedContent.trim()) {
    console.error("❌ Generated API types in src/lib/api-types.ts are out of date with docs/openapi.json!");
    console.error("👉 Run 'npm run generate:api-types' in frontend/ to update types.");
    process.exit(1);
  }

  console.log("✅ TypeScript API types are up to date with docs/openapi.json.");
  process.exit(0);
} catch (err) {
  console.error("Failed to verify API types:", err);
  process.exit(1);
}
