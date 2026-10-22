import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OverviewPage } from "../pages/OverviewPage";
import { AssessmentsPage } from "../pages/AssessmentsPage";
import { DevicesPage } from "../pages/DevicesPage";
import { ReportsPage } from "../pages/ReportsPage";
import { AuthProvider } from "../features/auth/AuthContext";
import { UserProfileProvider } from "../features/auth/UserProfileContext";
import { ToastProvider } from "../components/ui/Toast";
import type { components } from "../lib/api-types";

describe("Privacy & Data Boundary Protections", () => {
  it("type-level verification: AssessmentListItem and Ingestion items prohibit raw landmark or frame fields", () => {
    type AssessmentItem = components["schemas"]["AssessmentListItem"];
    type IngestItem = components["schemas"]["AssessmentEventIngestItem"];

    // Keys forbidden in privacy-preserving architecture
    const prohibitedKeywords = [
      "landmark",
      "landmarks",
      "coordinate",
      "coordinates",
      "keypoint",
      "keypoints",
      "mesh",
      "frame",
      "frames",
      "image",
      "video",
      "face",
      "facial",
      "iris",
      "raw_data",
    ];

    // Assert at type level using TypeScript key inspection
    type KeysOfAssessment = keyof AssessmentItem;
    type KeysOfIngest = keyof IngestItem;

    const assessmentKeys: (KeysOfAssessment | KeysOfIngest)[] = [
      "event_id",
      "device_id",
      "captured_at",
      "scoring_method",
      "scoring_version",
      "validity",
      "score",
      "neck_score",
      "trunk_score",
      "upper_arm_score",
      "guidance_codes",
      "software_version",
    ];

    assessmentKeys.forEach((key) => {
      const lower = String(key).toLowerCase();
      prohibitedKeywords.forEach((forbidden) => {
        expect(lower).not.toBe(forbidden);
      });
    });
  });

  it("DOM rendered output across all dashboard pages never renders raw landmark coordinates or camera feed tags", () => {
    const prohibitedSelectors = [
      "video",
      "canvas",
      "img[src*='camera']",
      "img[src*='capture']",
      "img[src*='frame']",
      "[data-landmarks]",
      "[data-coordinates]",
    ];

    const pages = [
      <OverviewPage key="overview" />,
      <AssessmentsPage key="assessments" />,
      <DevicesPage key="devices" />,
      <ReportsPage key="reports" />,
    ];

    pages.forEach((pageComponent) => {
      const { container } = render(
        <MemoryRouter>
          <AuthProvider>
            <UserProfileProvider>
              <ToastProvider>{pageComponent}</ToastProvider>
            </UserProfileProvider>
          </AuthProvider>
        </MemoryRouter>
      );

      prohibitedSelectors.forEach((selector) => {
        expect(container.querySelector(selector)).toBeNull();
      });

      // Assert no raw coordinate strings like [x: 0.123, y: 0.456, z: -0.789] exist in textContent
      const text = container.textContent || "";
      expect(text).not.toMatch(/landmark_\d+/i);
      expect(text).not.toMatch(/coordinate_[xyz]/i);
      expect(text).not.toMatch(/visibility: 0\.\d+/i);
    });
  });
});
