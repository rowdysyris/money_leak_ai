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
 * Return a positive or negative currency string.
 */
function signedCurrency(value) {
  const amount = toNumber(value);
  const prefix = amount > 0 ? "+" : "";
  return `${prefix}${formatCurrency(amount)}`;
}

/**
 * Render month-wise analytics and previous-month comparison.
 */
export default function MonthComparison() {
  const monthly = useApiResource("/api/insights/monthly-analysis", { initialData: { months: [], summary: {} } });
  const comparison = useApiResource("/api/insights/monthly-comparison", { initialData: { comparisons: [], insights: [] } });
  const explanation = useApiResource("/api/insights/monthly-change-explanation", { initialData: { drivers: [], category_drivers: [], merchant_drivers: [] } });
  const months = safeArray(monthly.data?.months);
  const comparisons = safeArray(comparison.data?.comparisons);
  const insights = safeArray(comparison.data?.insights);
  const explanationDrivers = safeArray(explanation.data?.drivers);
  const categoryDrivers = safeArray(explanation.data?.category_drivers);
  const merchantDrivers = safeArray(explanation.data?.merchant_drivers);
  const latest = months[months.length - 1] ?? null;
  const loading = monthly.loading || comparison.loading || explanation.loading;

  if (loading) {
    return <AppLayout title="Month Comparison" subtitle="Compare spending, income, leak score, and savings month by month."><SkeletonCard height="h-[620px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Month Comparison" subtitle="Compare spending, income, leak score, and savings month by month.">
      <div className="space-y-6">
        {monthly.error || comparison.error || explanation.error ? <ErrorBanner message={monthly.error || comparison.error || explanation.error} onRetry={() => { monthly.refetch(); comparison.refetch(); explanation.refetch(); }} /> : null}
        <WarningBanner warnings={[...(monthly.warnings ?? []), ...(comparison.warnings ?? []), ...(explanation.warnings ?? [])]} />

        {months.length === 0 ? (
          <EmptyState icon="calendar" title="No month data yet" description="Upload one or more statements to see month-wise comparison." actionLabel="Upload statements" onAction={() => { window.location.href = "/upload"; }} />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Months Detected" value={formatNumber(months.length)} subtitle="Calendar months in uploaded data" icon="calendar" />
              <MetricCard label="Latest Month Spend" value={formatCurrency(latest?.actionable_spend)} subtitle={latest?.label ?? "Latest month"} icon="target" color="text-blue-600" />
              <MetricCard label="Latest Income" value={formatCurrency(latest?.total_received)} subtitle="Credits detected that month" icon="income" color="text-green-600" />
              <MetricCard label="Latest Leak Score" value={formatNumber(latest?.money_leak_score)} subtitle="Lower is better" icon="alert" color={toNumber(latest?.money_leak_score) > 60 ? "text-red-600" : "text-green-600"} />
            </div>

            <SectionCard title="Month-wise analysis" subtitle="Each row uses transactions from that calendar month. Partial months are flagged.">
              <div className="table-scroll overflow-x-auto rounded-3xl border border-slate-100">
                <table className="min-w-[960px] w-full text-sm">
                  <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr><th className="px-4 py-3">Month</th><th className="px-4 py-3 text-right">Actionable Spend</th><th className="px-4 py-3 text-right">Received</th><th className="px-4 py-3 text-right">Net</th><th className="px-4 py-3">Top Category</th><th className="px-4 py-3 text-right">Leak Score</th><th className="px-4 py-3 text-right">Small Leakage</th><th className="px-4 py-3">Coverage</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {months.map((row) => (
                      <tr key={row.month} className="hover:bg-blue-50/40">
                        <td className="px-4 py-3 font-black">{row.label}</td>
                        <td className="px-4 py-3 text-right font-bold">{formatCurrency(row.actionable_spend)}</td>
                        <td className="px-4 py-3 text-right font-bold text-green-700">{formatCurrency(row.total_received)}</td>
                        <td className={`px-4 py-3 text-right font-bold ${toNumber(row.net_savings) >= 0 ? "text-green-700" : "text-red-600"}`}>{formatCurrency(row.net_savings)}</td>
                        <td className="px-4 py-3">{row.top_category}</td>
                        <td className="px-4 py-3 text-right font-bold">{formatNumber(row.money_leak_score)}</td>
                        <td className="px-4 py-3 text-right text-red-600 font-bold">{formatCurrency(row.small_spend_leakage)}</td>
                        <td className="px-4 py-3"><span className={`rounded-full px-3 py-1 text-xs font-black ${row.is_full_month ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{row.is_full_month ? "Full month" : `${row.days_covered} days`}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>



            <SectionCard title="What changed this month?" subtitle="Explains the latest month movement using category, merchant, income, and recurring-payment changes.">
              {explanationDrivers.length === 0 ? <EmptyState icon="brain" title="Need two months for explanation" description="Upload another statement month to explain what changed." /> : (
                <div className="grid gap-5 xl:grid-cols-[1fr_1.25fr]">
                  <div className="rounded-3xl bg-slate-950 p-5 text-white">
                    <p className="text-xs font-black uppercase tracking-wide text-blue-200">AI-style deterministic explanation</p>
                    <h2 className="mt-3 text-2xl font-black leading-tight">{explanation.data?.headline}</h2>
                    <ul className="mt-5 space-y-3 text-sm font-semibold leading-6 text-slate-300">
                      {explanationDrivers.slice(0, 5).map((item, index) => <li key={`${item}-${index}`} className="rounded-2xl bg-white/10 p-3">{item}</li>)}
                    </ul>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-3xl border border-slate-200 bg-white p-5">
                      <h3 className="font-black text-slate-950">Category drivers</h3>
                      <div className="mt-4 space-y-3">
                        {categoryDrivers.slice(0, 5).map((row) => (
                          <div key={`cat-${row.name}`} className="flex items-center justify-between gap-3 rounded-2xl bg-slate-50 p-3">
                            <span className="font-bold text-slate-700">{row.name}</span>
                            <span className={`font-black ${toNumber(row.change_amount) > 0 ? "text-red-600" : "text-green-700"}`}>{signedCurrency(row.change_amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-3xl border border-slate-200 bg-white p-5">
                      <h3 className="font-black text-slate-950">Merchant drivers</h3>
                      <div className="mt-4 space-y-3">
                        {merchantDrivers.slice(0, 5).map((row) => (
                          <div key={`merchant-${row.name}`} className="flex items-center justify-between gap-3 rounded-2xl bg-slate-50 p-3">
                            <span className="min-w-0 truncate font-bold text-slate-700">{row.name}</span>
                            <span className={`shrink-0 font-black ${toNumber(row.change_amount) > 0 ? "text-red-600" : "text-green-700"}`}>{signedCurrency(row.change_amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </SectionCard>

            <SectionCard title="Previous-period comparison" subtitle="Shows what improved or worsened from one month to the next.">
              {comparisons.length === 0 ? <EmptyState icon="trend-up" title="Need at least two months" description="Upload another statement month to compare progress." /> : (
                <div className="grid gap-4 lg:grid-cols-2">
                  {comparisons.map((row) => (
                    <div key={`${row.from_month}-${row.to_month}`} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <p className="text-sm font-bold text-slate-500">{row.from_label} → {row.to_label}</p>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">Spending change</p><p className={`text-xl font-black ${toNumber(row.spending_change) > 0 ? "text-red-600" : "text-green-700"}`}>{signedCurrency(row.spending_change)}</p><p className="text-xs text-slate-500">{formatPercent(row.spending_change_pct)}</p></div>
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">Savings change</p><p className={`text-xl font-black ${toNumber(row.savings_change) >= 0 ? "text-green-700" : "text-red-600"}`}>{signedCurrency(row.savings_change)}</p></div>
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">Income change</p><p className="text-xl font-black text-blue-600">{signedCurrency(row.income_change)}</p></div>
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">Leak score change</p><p className={`text-xl font-black ${toNumber(row.money_leak_score_change) <= 0 ? "text-green-700" : "text-red-600"}`}>{formatNumber(row.money_leak_score_change)}</p></div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {insights.length ? <div className="mt-5 rounded-3xl bg-blue-50 p-5 text-sm font-semibold text-blue-800"><ul className="list-disc space-y-2 pl-5">{insights.slice(0, 6).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div> : null}
            </SectionCard>
          </>
        )}
      </div>
    </AppLayout>
  );
}
