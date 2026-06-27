import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import WarningBanner from "../components/ui/WarningBanner";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatNumber, formatPercent, safeArray, toNumber } from "../utils/formatters";

/**
 * Return health score color classes.
 */
function healthTone(score) {
  const value = toNumber(score);
  if (value >= 80) return "text-green-700";
  if (value >= 65) return "text-blue-700";
  if (value >= 45) return "text-amber-700";
  return "text-red-600";
}

/**
 * Render one ratio bar.
 */
function RatioBar({ label, value, tone }) {
  const pct = Math.min(100, Math.max(0, toNumber(value)));
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-4">
      <div className="flex justify-between gap-3 text-sm font-black"><span>{label}</span><span>{formatPercent(pct)}</span></div>
      <div className="mt-3 h-3 rounded-full bg-slate-100"><div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

/**
 * Render income-aware health scoring.
 */
export default function FinancialHealth() {
  const health = useApiResource("/api/insights/financial-health-score", { initialData: {} });
  const data = health.data ?? {};
  const drivers = safeArray(data.drivers);

  if (health.loading) {
    return <AppLayout title="Financial Health" subtitle="Income-aware score using savings rate, wants, needs, waste, and EMI pressure."><SkeletonCard height="h-[560px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Financial Health" subtitle="Income-aware score using savings rate, wants, needs, waste, and EMI pressure.">
      <div className="space-y-6">
        {health.error ? <ErrorBanner message={health.error} onRetry={health.refetch} /> : null}
        <WarningBanner warnings={health.warnings ?? []} />
        {!data || Object.keys(data).length === 0 ? (
          <EmptyState icon="health" title="No health score yet" description="Upload statements to calculate income-aware financial health." />
        ) : (
          <>
            <section className="rounded-[2rem] bg-slate-950 p-6 text-white shadow-xl">
              <p className="text-sm font-black uppercase tracking-[0.25em] text-green-300">Financial health score</p>
              <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div><h2 className="text-5xl font-black">{formatNumber(data.score)}/100</h2><p className="mt-2 text-lg font-bold text-slate-300">{data.status}</p></div>
                <p className="max-w-2xl text-sm leading-6 text-slate-300">This score compares spending behavior against detected income, so it answers whether spending is sustainable, not just where money went.</p>
              </div>
            </section>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Detected Income" value={formatCurrency(data.income_total)} subtitle="Income-like credits in statement" icon="income" color="text-green-600" />
              <MetricCard label="Monthly Baseline" value={formatCurrency(data.monthly_income_baseline)} subtitle="Recurring income estimate" icon="receipt" color="text-blue-600" />
              <MetricCard label="Savings Rate" value={formatPercent(data.savings_rate_pct)} subtitle="Savings/investments to income" icon="savings" color="text-green-700" />
              <MetricCard label="Debt Pressure" value={formatPercent(data.debt_pressure_pct)} subtitle="EMI & loans to income" icon="bank" color={toNumber(data.debt_pressure_pct) > 35 ? "text-red-600" : "text-amber-700"} />
            </div>
            <SectionCard title="Income ratio breakdown" subtitle="Lower wants, waste, and debt ratios usually mean stronger financial health.">
              <div className="grid gap-4 md:grid-cols-2">
                <RatioBar label="Needs to income" value={data.needs_to_income_pct} tone="bg-blue-500" />
                <RatioBar label="Wants to income" value={data.wants_to_income_pct} tone="bg-purple-500" />
                <RatioBar label="Waste to income" value={data.waste_to_income_pct} tone="bg-red-500" />
                <RatioBar label="Savings to income" value={data.savings_rate_pct} tone="bg-green-500" />
              </div>
            </SectionCard>
            <SectionCard title="Why this score" subtitle="Transparent drivers used in the calculation.">
              <div className="grid gap-3 md:grid-cols-2">
                {drivers.map((driver, index) => <div key={`${driver}-${index}`} className="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-700">{driver}</div>)}
              </div>
            </SectionCard>
          </>
        )}
      </div>
    </AppLayout>
  );
}
