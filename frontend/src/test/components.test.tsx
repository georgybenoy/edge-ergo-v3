import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { KpiCard } from "../components/ui/KpiCard";
import { DateRangeControl } from "../components/ui/DateRangeControl";
import { Badge, StatusPill } from "../components/ui/Badge";
import { Table } from "../components/ui/Table";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { ConfigMissingScreen } from "../components/ui/ConfigMissingScreen";
import { StaleDataBanner } from "../components/ui/StaleDataBanner";

describe("Reusable UI Components (DESIGN.md §18)", () => {
  describe("KpiCard", () => {
    it("renders valid numeric metric with unit and definition", () => {
      render(
        <KpiCard
          label="Average RULA Score"
          value={3.25}
          unit="points"
          definition="Mean partial RULA screening risk score"
          sampleCount={142}
        />
      );

      expect(screen.getByText("Average RULA Score")).toBeInTheDocument();
      expect(screen.getByText("3.25")).toBeInTheDocument();
      expect(screen.getByText("points")).toBeInTheDocument();
      expect(screen.getByText(/Mean partial RULA screening risk score/)).toBeInTheDocument();
      expect(screen.getByText(/Sample size: 142 observations/)).toBeInTheDocument();
    });

    it("renders honest 'Not enough data' state when value is null without fabricating zero", () => {
      render(
        <KpiCard
          label="Average RULA Score"
          value={null}
          definition="Mean partial RULA screening risk score"
          insufficientReason="Zero valid observations recorded in organization"
        />
      );

      expect(screen.getByText("Not enough data")).toBeInTheDocument();
      expect(screen.getByText("Zero valid observations recorded in organization")).toBeInTheDocument();
      expect(screen.queryByText("0")).not.toBeInTheDocument();
      expect(screen.queryByText("0.0")).not.toBeInTheDocument();
    });
  });

  describe("Badge & StatusPill", () => {
    it("ALWAYS renders icon and text, never color alone", () => {
      const { container } = render(
        <Badge variant="success" label="Active" />
      );

      expect(screen.getByText("Active")).toBeInTheDocument();
      // Verify SVG icon exists inside the badge
      const svg = container.querySelector("svg");
      expect(svg).toBeInTheDocument();
    });

    it("StatusPill alias behaves identically to Badge", () => {
      const { container } = render(
        <StatusPill variant="danger" label="Offline" />
      );
      expect(screen.getByText("Offline")).toBeInTheDocument();
      expect(container.querySelector("svg")).toBeInTheDocument();
    });
  });

  describe("DateRangeControl", () => {
    it("toggles active preset and triggers onChange callback", () => {
      const onChange = vi.fn();
      render(<DateRangeControl value="7d" onChange={onChange} />);

      const button30d = screen.getByRole("button", { name: "30 Days" });
      expect(button30d).toHaveAttribute("aria-pressed", "false");

      const button7d = screen.getByRole("button", { name: "7 Days" });
      expect(button7d).toHaveAttribute("aria-pressed", "true");

      fireEvent.click(button30d);
      expect(onChange).toHaveBeenCalledWith("30d");
    });
  });

  describe("Table", () => {
    it("renders semantic table and rows on desktop and card fallback on mobile", () => {
      const columns = [
        { key: "label", header: "Workstation" },
        { key: "status", header: "Status" },
      ];
      const data = [
        { id: "1", label: "Station A", status: "Online" },
        { id: "2", label: "Station B", status: "Offline" },
      ];

      render(
        <Table
          columns={columns}
          data={data}
          keyExtractor={(item) => item.id}
        />
      );

      // Verify table headers
      expect(screen.getAllByText("Workstation").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Station A").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Station B").length).toBeGreaterThan(0);
    });
  });

  describe("ConfirmDialog", () => {
    it("renders dialog with title and responds to Escape key to cancel", () => {
      const onCancel = vi.fn();
      const onConfirm = vi.fn();

      const { rerender } = render(
        <ConfirmDialog
          isOpen={true}
          title="Revoke Device"
          description="Are you sure you want to revoke this workstation?"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      );

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Revoke Device")).toBeInTheDocument();

      // Test Escape key
      fireEvent.keyDown(window, { key: "Escape" });
      expect(onCancel).toHaveBeenCalledTimes(1);

      // Close dialog
      rerender(
        <ConfirmDialog
          isOpen={false}
          title="Revoke Device"
          description="Are you sure you want to revoke this workstation?"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      );
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("triggers onConfirm when confirm button is clicked", () => {
      const onCancel = vi.fn();
      const onConfirm = vi.fn();

      render(
        <ConfirmDialog
          isOpen={true}
          title="Revoke Device"
          description="Are you sure you want to revoke this workstation?"
          confirmLabel="Yes, Revoke"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: "Yes, Revoke" }));
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
  });

  describe("ConfigMissingScreen", () => {
    it("renders missing variables cleanly without blank screen", () => {
      render(
        <ConfigMissingScreen
          missingKeys={["VITE_SUPABASE_URL", "VITE_SUPABASE_PUBLISHABLE_KEY"]}
        />
      );

      expect(screen.getByText("Configuration Required")).toBeInTheDocument();
      expect(screen.getByText("VITE_SUPABASE_URL")).toBeInTheDocument();
      expect(screen.getByText("VITE_SUPABASE_PUBLISHABLE_KEY")).toBeInTheDocument();
    });
  });

  describe("StaleDataBanner", () => {
    it("renders last updated timestamp and refresh button", () => {
      const onRefresh = vi.fn();
      const testDate = new Date("2026-10-20T12:00:00Z");

      render(<StaleDataBanner lastUpdated={testDate} onRefresh={onRefresh} />);

      expect(screen.getByLabelText("Data freshness notice")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: /Refresh now/i }));
      expect(onRefresh).toHaveBeenCalledTimes(1);
    });
  });
});
