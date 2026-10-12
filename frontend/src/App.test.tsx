import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, afterEach } from "vitest";
import App from "./App";
import type { Portfolio } from "./types";

const apiMock = vi.hoisted(() => ({
  demo: vi.fn(),
  upload: vi.fn(),
  post: vi.fn(),
}));
afterEach(() => cleanup());

vi.mock("./api", () => ({ api: apiMock }));
vi.mock("./components/GraphView", () => ({
  GraphView: () => <div data-testid="graph-view" />,
}));

const portfolio: Portfolio = {
  name: "Test estate",
  synthetic: true,
  applications: [
    {
      application_id: "app-1",
      name: "Billing",
      business_domain: "Billing",
      business_criticality: "high",
      technical_debt_score: 7,
      migration_effort: 5,
      migration_risk: 4,
      migration_cost: 12000,
      dependencies: [],
    },
  ],
};

async function loadDemo() {
  const user = userEvent.setup();
  apiMock.demo.mockResolvedValue(portfolio);
  render(<App />);
  await user.click(screen.getByRole("button", { name: "Load 100-app demo" }));
  await screen.findByText("SYNTHETIC DEMONSTRATION DATA");
  return user;
}

describe("CloudMorph workflow controls", () => {
  beforeEach(() => {
    apiMock.demo.mockReset();
    apiMock.post.mockReset();
    apiMock.upload.mockReset();
  });

  it("migration optimizer controls send the selected objective and constraints", async () => {
    const user = await loadDemo();
    apiMock.post.mockImplementation(async (path: string) =>
      path === "/api/optimize"
        ? {
            status: "FEASIBLE",
            solver_used: "deterministic_fallback",
            waves: [],
          }
        : {
            plans_attempted: 0,
            unique_candidates: 0,
            duplicate_candidates_removed: 0,
            frontier_count: 0,
            frontier: [],
            axes_note: "",
          },
    );
    await user.click(
      screen.getByRole("button", { name: "Migration Wave Optimizer" }),
    );
    await user.selectOptions(
      screen.getByLabelText("Optimization objective"),
      "minimize_execution_risk",
    );
    await user.clear(screen.getByLabelText("Max waves"));
    await user.type(screen.getByLabelText("Max waves"), "6");
    await user.click(
      screen.getByRole("button", { name: "Generate valid waves" }),
    );
    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/optimize",
        expect.objectContaining({
          objective: "minimize_execution_risk",
          constraints: expect.objectContaining({ max_waves: 6 }),
        }),
      ),
    );
  });

  it("architecture strategy selector changes the architecture API request", async () => {
    const user = await loadDemo();
    apiMock.post.mockResolvedValue({
      application_id: "app-1",
      strategy: "Refactor",
      pattern: "modular monolith",
      components: [],
      warnings: [],
    });
    await user.click(
      screen.getByRole("button", { name: "Target Architecture" }),
    );
    await user.selectOptions(
      screen.getByLabelText("Architecture strategy"),
      "Refactor",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Generate provider-neutral architecture",
      }),
    );
    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/architecture",
        expect.objectContaining({
          strategy: "Refactor",
          application: expect.objectContaining({ application_id: "app-1" }),
        }),
      ),
    );
    expect(
      await screen.findByText("Refactor → modular monolith"),
    ).toBeInTheDocument();
  });

  it("cost strategy selector changes the cost request and comparison uses existing endpoint", async () => {
    const user = await loadDemo();
    apiMock.post.mockImplementation(async (path: string) => {
      if (path === "/api/cost/Retire")
        return {
          label: "ILLUSTRATIVE ESTIMATE",
          strategy: "Retire",
          monthly_run_cost_estimate: 10,
          migration_effort_cost_estimate: 20,
          annualized_first_year_estimate: 140,
          assumptions: {},
        };
      if (path === "/api/cost-compare")
        return {
          current_estate_monthly_input: 1000,
          alternatives: [
            {
              label: "ILLUSTRATIVE ESTIMATE",
              strategy: "Rehost",
              monthly_run_cost_estimate: 100,
              migration_effort_cost_estimate: 200,
              annualized_first_year_estimate: 1400,
              assumptions: {},
            },
          ],
          assumption_label: "ILLUSTRATIVE SAMPLE VALUES",
        };
      throw new Error(`unexpected ${path}`);
    });
    await user.click(screen.getByRole("button", { name: "Cost Model" }));
    await user.selectOptions(screen.getByLabelText("Cost strategy"), "Retire");
    await user.click(
      screen.getByRole("button", { name: "Estimate illustrative cost" }),
    );
    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/cost/Retire",
        expect.objectContaining({
          application: expect.objectContaining({ application_id: "app-1" }),
        }),
      ),
    );
    expect(
      await screen.findByText("ILLUSTRATIVE ESTIMATE · Retire"),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Compare all strategies" }),
    );
    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/cost-compare",
        expect.any(Object),
      ),
    );
  });
});
