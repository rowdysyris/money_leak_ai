import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "../api/client";
import ProtectedRoute from "../components/ProtectedRoute";
import MetricCard from "../components/ui/MetricCard";
import { ToastProvider } from "../components/ui/Toast";
import { AuthProvider } from "../context/AuthContext";
import useApiResource from "../hooks/useApiResource";
import Dashboard from "../pages/Dashboard";
import Transactions from "../pages/Transactions";
import Upload from "../pages/Upload";
import { formatCurrency, getLeakScoreColor } from "../utils/formatters";

vi.mock("../hooks/useApiResource", () => ({ default: vi.fn() }));
vi.mock("../api/client", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  getFriendlyErrorMessage: vi.fn(() => "Something went wrong. Please try again."),
  emitToast: vi.fn()
}));

/**
 * Store authenticated local state for protected page tests.
 */
function authenticate() {
  localStorage.setItem("access_token", "test-token");
  localStorage.setItem("auth_user", JSON.stringify({ id: "user-1", full_name: "Kedar", profile_type: "Student", city: "Bhopal" }));
}

/**
 * Render a component with router, auth, and toast providers.
 */
function renderWithProviders(element, initialPath = "/dashboard") {
  return render(
    <AuthProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={[initialPath]}>{element}</MemoryRouter>
      </ToastProvider>
    </AuthProvider>
  );
}

/**
 * Build a standard useApiResource payload.
 */
function resource(payload) {
  return { data: payload?.data ?? null, warnings: payload?.warnings ?? [], loading: payload?.loading ?? false, error: payload?.error ?? "", refetch: vi.fn(), setData: vi.fn() };
}

describe("MoneyLeak AI frontend", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("test_dashboard_renders_skeleton_while_loading", () => {
    authenticate();
    useApiResource.mockImplementation(() => resource({ loading: true }));
    renderWithProviders(<Dashboard />);
    expect(screen.getAllByTestId("skeleton-card").length).toBeGreaterThan(0);
  });

  it("test_dashboard_renders_empty_state_with_no_data", () => {
    authenticate();
    useApiResource.mockImplementation(() => resource({ data: null, warnings: ["No statement uploaded yet. Upload a bank statement to see insights."] }));
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Upload your bank statement to get started")).toBeInTheDocument();
  });

  it("test_dashboard_retry_refetches_every_resource", () => {
    authenticate();
    const refetches = [];
    useApiResource.mockImplementation((endpoint) => {
      const result = resource({
        data: endpoint === "/api/dashboard/summary" ? { saving_priority_list: [] } : [],
        error: endpoint === "/api/dashboard/category-breakdown" ? "The request took too long. Please try again." : ""
      });
      refetches.push(result.refetch);
      return result;
    });

    renderWithProviders(<Dashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(refetches).toHaveLength(5);
    refetches.forEach((refetch) => expect(refetch).toHaveBeenCalledTimes(1));
  });

  it("test_metric_card_displays_correct_value", () => {
    render(<MetricCard label="Total Spent" value="₹1,234" subtitle="This month" />);
    expect(screen.getByText("Total Spent")).toBeInTheDocument();
    expect(screen.getByText("₹1,234")).toBeInTheDocument();
  });

  it("test_category_correction_calls_api", async () => {
    authenticate();
    apiClient.patch.mockResolvedValue({ data: { success: true, data: {} } });
    useApiResource.mockImplementation(() => resource({
      data: [{ id: "tx-1", transaction_date: "2024-01-01", merchant: "Swiggy", description: "UPI/Swiggy", amount: -250, transaction_type: "debit", category: "Miscellaneous", category_confidence: 0.2, needs_review: true }]
    }));
    renderWithProviders(<Transactions />, "/transactions");
    await userEvent.selectOptions(screen.getByLabelText("Category for Swiggy"), "Food & Dining");
    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith("/api/transactions/tx-1/category", { category: "Food & Dining" }));
  });

  it("test_upload_rejects_pdf", async () => {
    authenticate();
    renderWithProviders(<Upload />, "/upload");
    const input = document.querySelector('input[type="file"]');
    const file = new File(["pdf"], "statement.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getAllByText("PDF isn't supported yet. Export your statement from your banking app as CSV or Excel.").length).toBeGreaterThan(0);
  });

  it("test_upload_rejects_file_over_limit", () => {
    authenticate();
    renderWithProviders(<Upload />, "/upload");
    const input = document.querySelector('input[type="file"]');
    const file = new File([new Uint8Array((10 * 1024 * 1024) + 1)], "large.csv", { type: "text/csv" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getAllByText("File is larger than the 10 MB upload limit.").length).toBeGreaterThan(0);
  });

  it("test_upload_shows_preview_after_success", async () => {
    authenticate();
    apiClient.post.mockResolvedValue({
      data: {
        success: true,
        data: {
          processed_rows: 1,
          skipped_rows: 0,
          statement_period: { start: "2024-01-01", end: "2024-01-01" },
          warnings: [],
          preview: [{ transaction_date: "2024-01-01", merchant: "Swiggy", description: "UPI/Swiggy", amount: -250, transaction_type: "debit" }]
        }
      }
    });
    renderWithProviders(<Upload />, "/upload");
    const input = document.querySelector('input[type="file"]');
    const file = new File(["Date,Description,Amount\n2024-01-01,Swiggy,-250"], "statement.csv", { type: "text/csv" });
    await userEvent.upload(input, file);
    fireEvent.click(screen.getByText("Upload and Analyze"));
    await waitFor(() => expect(screen.getByText("Swiggy")).toBeInTheDocument());
  });

  it("test_upload_confirms_low_confidence_column_mapping", async () => {
    authenticate();
    apiClient.post
      .mockResolvedValueOnce({ data: { success: true, data: {
        requires_column_mapping: true,
        parser_metadata: {
          mapping_confidence: 0.697,
          source_columns: ["Booking Date Field", "Transaction Details Extra", "Transaction Amount Value"],
          column_map: { date: "Booking Date Field", description: "Transaction Details Extra", amount: "Transaction Amount Value" }
        },
        warnings: [],
        preview: []
      } } })
      .mockResolvedValueOnce({ data: { success: true, data: { statement_id: "statement-1", processed_rows: 1, skipped_rows: 0, warnings: [], preview: [] } } });
    renderWithProviders(<Upload />, "/upload");
    const input = document.querySelector('input[type="file"]');
    await userEvent.upload(input, new File(["custom"], "custom.csv", { type: "text/csv" }));
    fireEvent.click(screen.getByText("Upload and Analyze"));
    expect(await screen.findByText("Confirm statement columns")).toBeInTheDocument();
    expect(screen.getByLabelText("Map date column")).toHaveValue("Booking Date Field");
    fireEvent.click(screen.getByText("Confirm mapping and process"));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("View Dashboard")).toBeInTheDocument();
  });

  it("test_transaction_date_filters_and_reset_empty_state", async () => {
    authenticate();
    useApiResource.mockImplementation(() => resource({ data: [
      { id: "jan", transaction_date: "2024-01-10", merchant: "January Shop", description: "January", amount: -100, transaction_type: "debit", category: "Shopping", category_confidence: 0.9 },
      { id: "feb", transaction_date: "2024-02-10", merchant: "February Shop", description: "February", amount: -100, transaction_type: "debit", category: "Shopping", category_confidence: 0.9 }
    ] }));
    renderWithProviders(<Transactions />, "/transactions");
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2024-02-01" } });
    expect(screen.queryByText("January Shop")).not.toBeInTheDocument();
    expect(screen.getByText("February Shop")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2024-01-01" } });
    expect(screen.getByText("No transactions found")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Reset filters"));
    expect(screen.getByText("January Shop")).toBeInTheDocument();
  });

  it("test_money_leak_score_shows_correct_color", () => {
    expect(getLeakScoreColor(20)).toContain("green");
    expect(getLeakScoreColor(45)).toContain("yellow");
    expect(getLeakScoreColor(75)).toContain("red");
  });

  it("test_currency_formatter_indian_format", () => {
    expect(formatCurrency(123456)).toBe("₹1,23,456");
  });

  it("test_protected_route_redirects_unauthenticated", () => {
    render(
      <AuthProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={["/dashboard"]}>
            <Routes>
              <Route path="/dashboard" element={<ProtectedRoute><div>Private Dashboard</div></ProtectedRoute>} />
              <Route path="/login" element={<div>Login Page</div>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </AuthProvider>
    );
    expect(screen.getByText("Login Page")).toBeInTheDocument();
  });
});
