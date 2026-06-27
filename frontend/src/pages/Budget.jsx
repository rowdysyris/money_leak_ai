import { useEffect, useMemo, useState } from "react";
import apiClient, { getFriendlyErrorMessage } from "../api/client";
import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import { useToast } from "../components/ui/Toast";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, safeArray, toNumber } from "../utils/formatters";

const BUDGET_FIELDS = [
  ["food_budget", "Food & Dining"],
  ["shopping_budget", "Shopping"],
  ["subscriptions_budget", "Subscriptions"],
  ["travel_budget", "Travel & Transport"],
  ["bills_budget", "Bills & Utilities"]
];

/**
 * Return progress bar styling for budget usage.
 */
function progressColor(status) {
  if (status === "exceeded") {
    return "bg-red-500";
  }
  if (status === "near_limit" || status === "warning") {
    return "bg-yellow-500";
  }
  if (status === "not_set") {
    return "bg-slate-300";
  }
  return "bg-green-500";
}

/**
 * Convert a backend budget object into editable input values.
 */
function valuesFromBudget(budget) {
  const nextValues = { total_monthly_limit: "", savings_target: "", food_budget: "", shopping_budget: "", subscriptions_budget: "", travel_budget: "", bills_budget: "" };
  Object.keys(nextValues).forEach((key) => {
    if (budget?.[key] !== null && budget?.[key] !== undefined) {
      nextValues[key] = String(budget[key]);
    }
  });
  return nextValues;
}

/**
 * Render a status label for one budget row.
 */
function BudgetStatusText({ row }) {
  if (!row || row.status === "not_set") {
    return <span className="text-slate-500">No limit set</span>;
  }
  if (row.status === "exceeded") {
    return <span className="text-red-600">{row.status_label ?? `Over budget by ${formatCurrency(Math.abs(toNumber(row.remaining)))}`}</span>;
  }
  if (row.status === "near_limit" || row.status === "warning") {
    return <span className="text-yellow-700">{row.status_label ?? `${formatCurrency(row.remaining)} left`}</span>;
  }
  return <span className="text-green-700">{row.status_label ?? `${formatCurrency(row.remaining)} left`}</span>;
}

/**
 * Build a preview status from unsaved input values.
 */
function previewStatus(spent, limitValue) {
  const limit = toNumber(limitValue);
  const amount = toNumber(spent);
  if (limit <= 0) {
    return null;
  }
  const remaining = limit - amount;
  const percentage = limit > 0 ? Math.min(100, Math.max(0, (amount / limit) * 100)) : 0;
  if (remaining < 0) {
    return { status: "exceeded", label: `Would be over by ${formatCurrency(Math.abs(remaining))}`, percentage };
  }
  if (percentage >= 90) {
    return { status: "near_limit", label: `Would be near limit · ${formatCurrency(remaining)} left`, percentage };
  }
  if (percentage >= 70) {
    return { status: "warning", label: `Would need watching · ${formatCurrency(remaining)} left`, percentage };
  }
  return { status: "ok", label: `Would be within budget · ${formatCurrency(remaining)} left`, percentage };
}

/**
 * Return a readable month label from YYYY-MM.
 */
function monthLabel(monthKey) {
  if (!monthKey) {
    return "Latest month";
  }
  const [year, month] = String(monthKey).split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  if (Number.isNaN(date.getTime())) {
    return monthKey;
  }
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(date);
}

/**
 * Render budget setup and selected-month budget status.
 */
export default function Budget() {
  const [selectedMonth, setSelectedMonth] = useState("");
  const [values, setValues] = useState({ total_monthly_limit: "", savings_target: "", food_budget: "", shopping_budget: "", subscriptions_budget: "", travel_budget: "", bills_budget: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [suggestionApplied, setSuggestionApplied] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");
  const { showToast } = useToast();
  const endpoint = selectedMonth ? `/api/budget/status?month=${selectedMonth}` : "/api/budget/status";
  const statusResource = useApiResource(endpoint, { initialData: null });
  const statusData = statusResource.data ?? {};
  const categoryRows = safeArray(statusData.category_status);
  const suggestedBudget = statusData.suggested_budget ?? {};

  useEffect(function hydrateBudgetValues() {
    if (statusData.budget) {
      setValues(valuesFromBudget(statusData.budget));
    }
    if (!selectedMonth && statusData.month) {
      setSelectedMonth(statusData.month);
    }
  }, [statusData.budget, statusData.month]);

  const noBudgetSet = !statusData.has_budget;
  const totalSpent = useMemo(() => categoryRows.reduce((sum, row) => sum + toNumber(row?.spent), 0), [categoryRows]);
  const inputMonthlyLimit = toNumber(values.total_monthly_limit);
  const selectedLimit = toNumber(statusData.total_status?.limit) || inputMonthlyLimit;
  const overLimitAmount = selectedLimit > 0 ? totalSpent - selectedLimit : 0;
  const reductionPct = overLimitAmount > 0 && totalSpent > 0 ? (overLimitAmount / totalSpent) * 100 : 0;

  /**
   * Update a budget input value.
   */
  function updateValue(key, value) {
    setSavedMessage("");
    setValues((previous) => ({ ...previous, [key]: value }));
  }

  /**
   * Save the budget setup to the backend.
   */
  async function handleSave() {
    setSaving(true);
    setError("");
    const allowedKeys = ["total_monthly_limit", "savings_target", ...BUDGET_FIELDS.map(([key]) => key)];
    const payload = Object.fromEntries(allowedKeys.map((key) => [key, values[key] === "" ? null : Number(values[key]) ]));
    try {
      await apiClient.post("/api/budget/setup", payload);
      setSuggestionApplied(false);
      setSavedMessage(`Budget saved for ${monthLabel(selectedMonth || statusData.month)}.`);
      showToast({ type: "success", message: "Budget saved." });
      statusResource.refetch();
    } catch (requestError) {
      const message = getFriendlyErrorMessage(requestError);
      setError(message);
      showToast({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  /**
   * Fill input fields with backend suggested budgets.
   */
  function applySuggestedBudget() {
    const allowedKeys = ["total_monthly_limit", "savings_target", ...BUDGET_FIELDS.map(([key]) => key)];
    const cleanSuggestion = Object.fromEntries(allowedKeys.map((key) => [key, suggestedBudget[key] === null || suggestedBudget[key] === undefined ? "" : String(suggestedBudget[key]) ]));
    setValues((previous) => ({
      ...previous,
      ...cleanSuggestion
    }));
    setSuggestionApplied(true);
    setSavedMessage("");
    showToast({ type: "success", message: "Suggested budget generated. Review and click Save Budget." });
  }

  if (statusResource.loading) {
    return <AppLayout title="Budget" subtitle="Set monthly limits and track spend against them."><SkeletonCard height="h-[540px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Budget" subtitle="Set monthly limits and track selected-month spend against them.">
      <div className="space-y-6">
        {statusResource.error ? <ErrorBanner message={statusResource.error} onRetry={statusResource.refetch} /> : null}
        {error ? <ErrorBanner message={error} /> : null}
        {noBudgetSet ? (
          <div className="rounded-3xl border border-blue-200 bg-blue-50 p-5 text-sm text-blue-900">
            <p className="font-black">No budget set yet.</p>
            <p className="mt-1">Use the suggested budget or enter your own limits to start tracking overspending.</p>
          </div>
        ) : null}
        {suggestionApplied ? <div className="rounded-3xl border border-green-200 bg-green-50 p-5 text-sm font-bold text-green-800">Suggested budget generated. Review the limits, check the preview, then click Save Budget to apply it.</div> : null}
        {savedMessage ? <div className="rounded-3xl border border-green-200 bg-green-50 p-5 text-sm font-bold text-green-800">{savedMessage}</div> : null}

        <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
          <SectionCard title="Budget Setup" subtitle="Set monthly spending limits for each category and track your progress.">
            <div className="mb-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
              <p className="font-black text-slate-950">Budget month</p>
              <select value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 font-bold">
                {safeArray(statusData.available_months).length === 0 ? <option value={statusData.month ?? ""}>{monthLabel(statusData.month)}</option> : null}
                {safeArray(statusData.available_months).map((month) => <option key={month} value={month}>{monthLabel(month)}</option>)}
              </select>
            </div>

            <div className="mb-4 grid gap-3 sm:grid-cols-2">
              <button type="button" onClick={applySuggestedBudget} className="rounded-2xl border border-green-200 bg-green-50 px-4 py-3 text-sm font-black text-green-700 hover:bg-green-100">Generate Suggested Budget</button>
              <button type="button" onClick={() => setValues(valuesFromBudget({}))} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-black text-slate-600 hover:bg-slate-50">Clear Inputs</button>
            </div>

            <div className="space-y-4">
              <label className="block text-sm font-bold text-slate-700">Monthly spending limit after savings
                <input type="number" value={values.total_monthly_limit} onChange={(event) => updateValue("total_monthly_limit", event.target.value)} placeholder={suggestedBudget.total_monthly_limit ? `Suggested ${formatCurrency(suggestedBudget.total_monthly_limit)}` : "No limit set"} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3" />
              </label>
              <label className="block text-sm font-bold text-slate-700">Savings target from detected income
                <input type="number" value={values.savings_target} onChange={(event) => updateValue("savings_target", event.target.value)} placeholder={suggestedBudget.savings_target ? `Suggested ${formatCurrency(suggestedBudget.savings_target)}` : "No target set"} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3" />
              </label>
              {BUDGET_FIELDS.map(([key, label]) => (
                <label key={key} className="block text-sm font-bold text-slate-700">{label} budget
                  <input type="range" min="0" max="50000" step="500" value={values[key] || 0} onChange={(event) => updateValue(key, event.target.value)} className="mt-3 w-full" />
                  <input type="number" value={values[key]} onChange={(event) => updateValue(key, event.target.value)} placeholder={suggestedBudget[key] ? `Suggested ${formatCurrency(suggestedBudget[key])}` : "No limit set"} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3" />
                </label>
              ))}
              <button type="button" onClick={handleSave} disabled={saving} className="w-full rounded-2xl bg-blue-500 px-5 py-3 font-black text-white hover:bg-blue-600 disabled:opacity-50">
                {saving ? "Saving..." : "Save Budget"}
              </button>
            </div>
          </SectionCard>

          <SectionCard title={`Budget Status · ${monthLabel(statusData.month)}`} subtitle="Spend is calculated for the selected month only, not the full uploaded period.">
            <div className="mb-5 grid gap-4 sm:grid-cols-3">
              <MetricCard label="Selected Month Spend" value={formatCurrency(totalSpent)} color="text-blue-600" />
              <MetricCard label="Monthly Limit" value={statusData.total_status?.limit ? formatCurrency(statusData.total_status.limit) : "No limit set"} color="text-blue-600" />
              <MetricCard label="Savings Target" value={statusData.savings_progress?.target ? formatCurrency(statusData.savings_progress.target) : "No target set"} color="text-green-600" />
            </div>
            {selectedLimit > 0 ? (
              <div className={`mb-5 rounded-3xl p-4 text-sm font-bold ${overLimitAmount > 0 ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
                {overLimitAmount > 0 ? `Selected month spend is ${formatCurrency(overLimitAmount)} above the monthly limit. Required reduction: ${reductionPct.toFixed(1)}%.` : `Selected month spend is within the monthly limit by ${formatCurrency(Math.abs(overLimitAmount))}.`}
              </div>
            ) : null}

            {categoryRows.length === 0 ? <EmptyState icon="chart" title="No monthly transactions found" description="Budget status appears after transactions exist for the selected month." /> : (
              <div className="space-y-4">
                {categoryRows.map((row) => {
                  const field = BUDGET_FIELDS.find(([, label]) => label === row?.category)?.[0];
                  const unsavedPreview = suggestionApplied && field ? previewStatus(row?.spent, values[field]) : null;
                  const limit = row?.limit;
                  const percent = toNumber(row?.percentage_used);
                  return (
                    <div key={row?.category} className="rounded-2xl border border-slate-200 p-4">
                      <div className="flex items-start justify-between gap-4 text-sm">
                        <div>
                          <p className="font-black text-slate-950">{row?.category}</p>
                          <p className="mt-1 text-xs font-bold"><BudgetStatusText row={row} /></p>
                          {unsavedPreview ? <p className="mt-1 text-xs font-bold text-blue-700">Preview: {unsavedPreview.label}</p> : null}
                        </div>
                        <div className="text-right">
                          <p className="font-black text-slate-950">{formatCurrency(row?.spent)}</p>
                          <p className="text-xs font-bold text-slate-500">{limit ? `Limit ${formatCurrency(limit)}` : "No limit set"}</p>
                        </div>
                      </div>
                      <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100"><div className={`h-full ${progressColor(row?.status)}`} style={{ width: `${limit ? Math.min(100, percent) : 100}%` }} /></div>
                      <div className="mt-2 flex items-center justify-between text-xs font-bold text-slate-500">
                        <span>{limit ? `${percent.toFixed(1)}% used` : "Set a limit to track progress"}</span>
                        <Badge label={row?.status === "not_set" ? "No limit" : row?.status === "exceeded" ? "Over budget" : row?.status === "near_limit" ? "Near limit" : row?.status === "warning" ? "Watch" : "Within budget"} type={row?.status === "exceeded" ? "high" : row?.status === "warning" || row?.status === "near_limit" ? "medium" : "low"} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </AppLayout>
  );
}
