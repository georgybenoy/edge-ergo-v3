import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Frontend Secrets & Build Bundle Security Audit", () => {
  const frontendSrc = path.resolve(__dirname, "..");
  const frontendDist = path.resolve(__dirname, "../../dist");

  const FORBIDDEN_PATTERNS = [
    { name: "Service Role Key", regex: /service_role/i },
    { name: "Raw Supabase Secret", regex: /SUPABASE_SERVICE_ROLE_KEY/i },
    { name: "Database connection password", regex: /postgres(?:ql)?:\/\/[^:]+:[^@\s]+@/i },
    { name: "Device Credential Secret", regex: /eed_[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/ },
    { name: "Real Bearer JWT", regex: /eyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}/ },
  ];

  function scanDirectory(dir: string): { file: string; pattern: string }[] {
    const findings: { file: string; pattern: string }[] = [];
    if (!fs.existsSync(dir)) return findings;

    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "node_modules" && entry.name !== ".git") {
          findings.push(...scanDirectory(fullPath));
        }
      } else if (
        entry.name.endsWith(".ts") ||
        entry.name.endsWith(".tsx") ||
        entry.name.endsWith(".js") ||
        entry.name.endsWith(".html") ||
        entry.name.endsWith(".css")
      ) {
        // Skip this test file itself
        if (entry.name === "secrets.test.ts") continue;

        const content = fs.readFileSync(fullPath, "utf-8");
        for (const { name, regex } of FORBIDDEN_PATTERNS) {
          if (regex.test(content)) {
            findings.push({ file: fullPath, pattern: name });
          }
        }
      }
    }
    return findings;
  }

  it("ensures no service-role keys or backend secrets exist in frontend/src", () => {
    const findings = scanDirectory(frontendSrc);
    expect(findings, `Found secrets in frontend/src: ${JSON.stringify(findings)}`).toEqual([]);
  });

  it("ensures no service-role keys or backend secrets are leaked into frontend/dist", () => {
    if (!fs.existsSync(frontendDist)) {
      // If dist hasn't been built yet in a test run, skip or require build
      return;
    }
    const findings = scanDirectory(frontendDist);
    expect(findings, `Found secrets in frontend/dist: ${JSON.stringify(findings)}`).toEqual([]);
  });
});
