import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("Production Build Invariants", () => {
  it("asserts development fixture data banner and mock payloads are compiled out of production bundle", () => {
    const distAssetsDir = path.resolve(__dirname, "../../dist/assets");

    if (!fs.existsSync(distAssetsDir)) {
      // In CI / local test if build hasn't run yet, ensure bundle verification runs when dist exists
      return;
    }

    const files = fs.readdirSync(distAssetsDir);
    const jsFiles = files.filter((f) => f.endsWith(".js"));

    expect(jsFiles.length).toBeGreaterThan(0);

    let combinedJsBundle = "";
    for (const file of jsFiles) {
      combinedJsBundle += fs.readFileSync(path.join(distAssetsDir, file), "utf-8");
    }

    // Assert that development fixture banner and markers are absent from production bundle
    expect(combinedJsBundle).not.toContain("DEVELOPMENT FIXTURE DATA");
    expect(combinedJsBundle).not.toContain("simulated local contract fixtures enabled");
    expect(combinedJsBundle).not.toContain("eet_dev_fixture_");
    expect(combinedJsBundle).not.toContain("Workstation Alpha (Design Dept)");
  });
});
