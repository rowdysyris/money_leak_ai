import { useState } from "react";
import apiClient, { getFriendlyErrorMessage } from "../api/client";
import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import WarningBanner from "../components/ui/WarningBanner";
import { useToast } from "../components/ui/Toast";
import { formatCurrency, safeArray, toNumber } from "../utils/formatters";

const QUICK_GOALS = [
  { goal_name: "Emergency fund", target_amount: 50000, months: 6 },
  { goal_name: "Laptop", target_amount: 90000, months: 9 },
  { goal_name: "Trip", target_amount: 30000, months: 4 },
  { goal_name: "Phone upgrade", target_amount: 70000, months: 6 }
];

/**
 * Render goal planner page.
 */
export default function GoalPlanner() {
  const [form, setForm] = useState({ goal_name: "Emergency fund", target_amount: 50000, months: 6 });
  const [result, setResult] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { showToast } = useToast();

  /**
   * Update one form field.
   */
  function updateField(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
  }

  /**
   * Request a plan from the backend.
   */
  async function generatePlan() {
    setLoading(true);
    setError("");
    try {
      const payload = { goal_name: form.goal_name, target_amount: toNumber(form.target_amount), months: Math.max(1, Number(form.months || 1)) };
      const response = await apiClient.post("/api/goals/plan", payload);
      setResult(response?.data?.data ?? null);
      setWarnings(response?.data?.warnings ?? []);
      showToast({ type: "success", message: "Goal plan generated." });
    } catch (requestError) {
      const message = getFriendlyErrorMessage(requestError);
      setError(message);
      showToast({ type: "error", message });
    } finally {
      setLoading(false);
    }
  }

  const actions = safeArray(result?.actions);

  return (
    <AppLayout title="Goal Planner" subtitle="Turn leak detection into a concrete savings plan for a phone, trip, laptop, or emergency fund.">
      <div className="space-y-6">
        {error ? <ErrorBanner message={error} /> : null}
        <WarningBanner warnings={warnings} />
        <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
          <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-xl font-black text-slate-950">Create a goal</h2>
            <p className="mt-2 text-sm text-slate-500">Enter target amount and timeline. MoneyLeak AI maps your current saving opportunities to the goal.</p>
            <label className="mt-5 block text-sm font-bold text-slate-700">Goal name
              <input value={form.goal_name} onChange={(event) => updateField("goal_name", event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3" />
            </label>
            <label className="mt-4 block text-sm font-bold text-slate-700">Target amount
              <input type="number" min="0" value={form.target_amount} onChange={(event) => updateField("target_amount", event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3" />
            </label>
            <label className="mt-4 block text-sm font-bold text-slate-700">Timeline in months
              <input type="number" min="1" max="120" value={form.months} onChange={(event) => updateField("months", event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3" />
            </label>
            <button type="button" onClick={generatePlan} disabled={loading} className="mt-5 w-full rounded-2xl bg-blue-500 px-5 py-3 font-black text-white hover:bg-blue-600 disabled:opacity-50">{loading ? "Generating..." : "Generate Plan"}</button>
            <div className="mt-5 grid gap-2">
              {QUICK_GOALS.map((goal) => <button type="button" key={goal.goal_name} onClick={() => setForm(goal)} className="rounded-2xl bg-slate-50 px-4 py-3 text-left text-sm font-bold text-slate-700 hover:bg-blue-50">{goal.goal_name} · {formatCurrency(goal.target_amount)} in {goal.months} months</button>)}
            </div>
          </div>
          <div className="space-y-4">
            {loading ? (
              <SkeletonCard height="h-[420px]" />
            ) : !result ? (
              <EmptyState icon="target" title="Add your first financial goal" description="Choose a target and timeline to generate a savings plan." />
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <MetricCard label="Required Monthly" value={formatCurrency(result.required_monthly_saving)} subtitle="To hit your target" icon="pin" color="text-blue-600" />
                  <MetricCard label="Possible Monthly" value={formatCurrency(result.possible_monthly_saving)} subtitle="From detected recommendations" icon="check" color="text-green-600" />
                  <MetricCard label="Remaining Gap" value={formatCurrency(result.remaining_monthly_gap)} subtitle={result.feasibility} icon="scale" color={toNumber(result.remaining_monthly_gap) > 0 ? "text-red-600" : "text-green-700"} />
                  <MetricCard label="Timeline" value={`${result.months} months`} subtitle={result.goal_name} icon="calendar" />
                </div>
                <SectionCard title="Recommended plan" subtitle="Start with the highest-impact actions first.">
                  <div className="grid gap-4 md:grid-cols-2">
                    {actions.map((action, index) => (
                      <div key={`${action.title}-${index}`} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <div className="flex items-start justify-between gap-3"><h3 className="text-lg font-black text-slate-950">#{index + 1} {action.title}</h3><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-600">{action.difficulty}</span></div>
                        <p className="mt-3 text-sm leading-6 text-slate-600">{action.action}</p>
                        <p className="mt-4 rounded-2xl bg-green-50 px-4 py-3 text-xl font-black text-green-700">{formatCurrency(action.monthly_saving)} / month</p>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              </>
            )}
          </div>
        </section>
      </div>
    </AppLayout>
  );
}
