import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DashboardFailedAlert } from "@/components/jobs/dashboard-run-controls";
import enMessages from "@/messages/en.json";

describe("DashboardFailedAlert", () => {
  it("renders the failed alert banner with title, message, and link to find-jobs", () => {
    render(
      <DashboardFailedAlert
        copy={{
          title: enMessages.dashboard.failedAlertTitle,
          message: enMessages.dashboard.failedAlertBody,
          action: enMessages.dashboard.editPreferences,
        }}
      />
    );

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText(enMessages.dashboard.failedAlertTitle)).toBeInTheDocument();
    expect(screen.getByText(enMessages.dashboard.failedAlertBody)).toBeInTheDocument();

    const link = screen.getByRole("link", { name: enMessages.dashboard.editPreferences });
    expect(link).toHaveAttribute("href", "/find-jobs");
  });
});
