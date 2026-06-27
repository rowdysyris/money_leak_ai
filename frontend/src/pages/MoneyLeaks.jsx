import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import AppIcon from "../components/ui/AppIcon";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatPercent, safeArray, toNumber } from "../utils/formatters";

/**
 * Return readable merchant names for bucket cards.
 */
function displayMerchant(value) {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "unknown") {
    return "Unidentified merchant";
  }
  return text;
}

/**
 * Return a comma-separated list of top bucket merchants.
 */
function bucketMerchantNames(topMerchants) {
  return safeArray(topMerchants)
    .slice(0, 3)
    .map((merchant) => displayMerchant(typeof merchant === "string" ? merchant : merchant?.merchant))
    .filter(Boolean)
    .join(", ");
}

/**
 * Return visual tone for a leakage bucket.
 */
function bucketTone(severity) {
  if (severity === "high") {
    return { bg: "bg-red-50", text: "text-red-600", border: "border-red-100", label: "High leak" };
  }
  if (severity === "medium") {
    return { bg: "bg-orange-50", text: "text-orange-600", border: "border-orange-100", label: "Medium leak" };
  }
  return { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-100", label: "Low leak" };
}

/**
 * Render an amount bucket card.
 */
function BucketCard({ title, bucket, severity }) {
  const tone = bucketTone(severity);
  return (
    <div className={`rounded-[1.75rem] border ${tone.border} ${tone.bg} p-5 shadow-sm`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-black text-slate-600">{title}</p>
          <p className={`mt-2 text-3xl font-black ${tone.text}`}>{formatCurrency(bucket?.total ?? 0)}</p>
        </div>
        <span className={`rounded-full bg-white px-3 py-1 text-xs font-black ${tone.text}`}>{tone.label}</span>
      </div>
      <p className="mt-1 text-sm font-semibold text-slate-600">{bucket?.count ?? 0} transactions</p>
      <p className="mt-3 text-xs leading-5 text-slate-500">Top merchants: {bucketMerchantNames(bucket?.top_merchants) || "—"}</p>
    </div>
  );
}

/**
 * Return a duplicate confidence label.
 */
function duplicateConfidence(confidence) {
  const value = toNumber(confidence);
  if (value >= 0.9) {
    return "Exact duplicate";
  }
  if (value >= 0.7) {
    return "Near duplicate";
  }
  return "Review duplicate";
}

/**
 * Render the Money Leaks page.
 */
export default function MoneyLeaks() {
  const smallLeaks = useApiResource("/api/insights/small-spend-leaks");
  const duplicates = useApiResource("/api/insights/duplicates", { initialData: [] });
  const yearlyImpact = useApiResource("/api/insights/yearly-impact", { initialData: [] });
  const savingPriority = useApiResource("/api/insights/saving-priority-list", { initialData: [] });
  const loading = smallLeaks.loading || duplicates.loading || yearlyImpact.loading || savingPriority.loading;
  const error = smallLeaks.error || duplicates.error || yearlyImpact.error || savingPriority.error;
  const buckets = smallLeaks.data?.buckets ?? smallLeaks.data ?? {};
  const bucketUnder100 = buckets?.under_100 ?? buckets?.bucket_under_100 ?? buckets?.bucket_1;
  const bucket100To200 = buckets?.between_100_200 ?? buckets?.bucket_100_to_200 ?? buckets?.bucket_2;
  const bucket200To500 = buckets?.between_200_500 ?? buckets?.bucket_200_to_500 ?? buckets?.bucket_3;
  const duplicateRows = safeArray(duplicates.data);
  const yearlyRows = safeArray(yearlyImpact.data);
  const recommendations = safeArray(savingPriority.data);
  const afterSaving = recommendations.reduce((sum, item) => sum + Number(item?.possible_monthly_saving ?? 0), 0);
  const yearlySaving = recommendations.reduce((sum, item) => sum + Number(item?.possible_yearly_saving ?? 0), 0);
  const topAction = recommendations[0]?.target ?? "—";
  const smallLeakage = toNumber(smallLeaks.data?.total_leakage);
  const smallLeakageSaving = toNumber(smallLeaks.data?.possible_monthly_saving);
  const projectedSmallLeakageAfter = Math.max(0, smallLeakage - smallLeakageSaving);
  const transactionCount = smallLeaks.data?.total_transactions ?? 0;

  if (loading) {
    return <AppLayout title="Money Leaks" subtitle="Hidden waste, duplicate payments, and small-spend leakage."><SkeletonCard height="h-[620px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Money Leaks" subtitle="Hidden waste, duplicate payments, and small-spend leakage.">
      <div className="space-y-6">
        {error ? <ErrorBanner message={error} onRetry={smallLeaks.refetch} /> : null}

        <section className="border border-slate-800 bg-slate-950 p-6 text-white">
          <div className="grid gap-4 md:grid-cols-4">
            <div className="md:col-span-2">
              <p className="text-sm font-black uppercase tracking-[0.25em] text-blue-200">Leakage command center</p>
              <h2 className="mt-3 text-3xl font-black">{formatCurrency(afterSaving)} monthly savings identified</h2>
              <p className="mt-2 text-sm leading-6 text-blue-100">Highest impact: {topAction}. Focus on frequent small debits before cutting essential expenses.</p>
            </div>
            <div className="rounded-3xl bg-white/10 p-4 ring-1 ring-white/15"><p className="text-sm font-bold text-blue-100">Yearly savings potential</p><p className="mt-2 text-2xl font-black">{formatCurrency(yearlySaving)}</p><p className="mt-1 text-xs text-blue-100">All detected actions combined</p></div>
            <div className="rounded-3xl bg-white/10 p-4 ring-1 ring-white/15"><p className="text-sm font-bold text-blue-100">Small transactions</p><p className="mt-2 text-2xl font-black">{transactionCount}</p><p className="mt-1 text-xs text-blue-100">Transactions below ₹500</p></div>
          </div>
        </section>

        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Estimated Monthly Savings" value={formatCurrency(afterSaving)} subtitle="Across all detected recommendations" icon="check" color="text-green-600" />
          <MetricCard label="Estimated Yearly Savings" value={formatCurrency(yearlySaving)} subtitle="Projected annual opportunity" icon="trend-up" color="text-blue-600" />
          <MetricCard label="Highest Impact" value={topAction} subtitle="Start here first" icon="target" color="text-slate-950" />
          <MetricCard label="Small Transactions" value={transactionCount} subtitle="Below ₹500" icon="coins" color="text-red-500" />
        </div>

        <section>
          <h2 className="mb-4 text-xl font-black text-slate-950">Small UPI Leakage</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <BucketCard title="Under ₹100" bucket={bucketUnder100} severity="low" />
            <BucketCard title="₹100–200" bucket={bucket100To200} severity="medium" />
            <BucketCard title="₹200–500" bucket={bucket200To500} severity="high" />
          </div>
          <p className="mt-4 rounded-3xl border border-blue-100 bg-blue-50 p-4 text-sm font-semibold leading-6 text-blue-700">
            You spent {formatCurrency(smallLeakage)} across {transactionCount} small transactions. Reducing these by 30% can save about {formatCurrency(smallLeakageSaving)}/month.
          </p>
        </section>

        <SectionCard title="Duplicate Payments" subtitle="Likely accidental repeats with reason and confidence.">
          {duplicateRows.length === 0 ? <EmptyState icon="check" title="No duplicates detected" description="Likely duplicate payments will appear here." /> : (
            <div className="table-scroll overflow-x-auto rounded-3xl border border-slate-100">
              <table className="min-w-[760px] w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Merchant</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Reason</th><th className="px-4 py-3">Action</th></tr></thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {duplicateRows.map((row, index) => {
                    const confidence = toNumber(row?.confidence_score ?? row?.confidence ?? 0);
                    return (
                      <tr key={`${row?.merchant}-${index}`}>
                        <td className="px-4 py-3 font-black">{displayMerchant(row?.merchant)}</td>
                        <td className="px-4 py-3 text-right font-black text-red-500">{formatCurrency(row?.amount)}</td>
                        <td className="px-4 py-3">{row?.duplicate_date ?? row?.date ?? "—"}</td>
                        <td className="px-4 py-3"><Badge label={`${duplicateConfidence(confidence)} · ${formatPercent(confidence * 100)}`} type={confidence >= 0.9 ? "high" : "medium"} /></td>
                        <td className="px-4 py-3 text-slate-500">{row?.reason ?? "Same merchant and amount pattern"}</td>
                        <td className="px-4 py-3"><button type="button" className="rounded-full border border-slate-200 px-3 py-2 text-xs font-bold hover:bg-slate-50">Mark as False Positive</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Possible Waste" subtitle="Ranked by controllability, impact, and how quickly the user can act.">
          {recommendations.length === 0 ? <EmptyState icon="waste" title="No waste recommendations yet" description="Bank charges, duplicate payments, and high-value miscellaneous spend will appear here." /> : (
            <div className="grid gap-4 md:grid-cols-2">
              {recommendations.map((item, index) => {
                const icon = String(item?.target ?? "").toLowerCase().includes("bank") ? "bank" : String(item?.target ?? "").toLowerCase().includes("duplicate") ? "copy" : String(item?.target ?? "").toLowerCase().includes("subscription") || String(item?.target ?? "").toLowerCase().includes("netflix") ? "repeat" : "coins";
                return (
                  <div key={`${item?.target}-${index}`} className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <span className="icon-well grid h-11 w-11 place-items-center"><AppIcon name={icon} size={20} /></span>
                        <div>
                          <p className="text-xs font-black uppercase tracking-wide text-slate-400">Rank #{item?.rank ?? index + 1}</p>
                          <h3 className="mt-1 font-black text-slate-950">{item?.target ?? item?.target_category ?? item?.action ?? "Possible waste"}</h3>
                        </div>
                      </div>
                      <Badge label={item?.difficulty ?? "medium"} type={item?.difficulty ?? "medium"} />
                    </div>
                    <p className="mt-4 text-sm font-semibold leading-6 text-slate-600">{item?.reason ?? "Reduce this to save money."}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-500">Action: {item?.action ?? "Review this spending area."}</p>
                    <div className="mt-4 grid gap-2 sm:grid-cols-2">
                      <p className="rounded-2xl bg-green-50 p-3 text-sm font-black text-green-700">{formatCurrency(item?.possible_monthly_saving)} / month</p>
                      <p className="rounded-2xl bg-blue-50 p-3 text-sm font-black text-blue-700">{formatCurrency(item?.possible_yearly_saving)} / year</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>

        <SectionCard title="Projected Annual Category Spend" subtitle="Annualized from the main statement period after excluding date outliers and anomalies.">
          {yearlyRows.length === 0 ? <EmptyState icon="trend-up" title="No yearly impact yet" description="Annualized category projections appear after upload." /> : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {yearlyRows.slice(0, 6).map((row, index) => (
                <div key={row?.category} className={`rounded-3xl p-5 ${index < 3 ? "bg-red-50" : "bg-slate-50"}`}>
                  <p className="text-sm font-bold text-slate-500">Projected annual spend</p>
                  <p className={`mt-2 text-2xl font-black ${index < 3 ? "text-red-500" : "text-slate-950"}`}>{formatCurrency(row?.yearly_amount ?? row?.annualized_amount)}</p>
                  <p className="mt-1 font-black text-slate-950">on {row?.category ?? "this category"} per year</p>
                  <p className="mt-2 text-xs font-semibold text-slate-500">Basis: annualized from the selected statement period.</p>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="Before vs After" subtitle="Small-spend reduction is separated from total estimated monthly savings.">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl bg-red-50 p-6"><p className="text-sm font-bold text-red-600">Detected Monthly Leakage</p><p className="mt-2 text-3xl font-black text-red-600">{formatCurrency(smallLeakage)}</p><p className="mt-1 text-sm text-red-700">Current small-spend leakage</p></div>
            <div className="rounded-3xl bg-blue-50 p-6"><p className="text-sm font-bold text-blue-600">After 30% Small-Spend Cut</p><p className="mt-2 text-3xl font-black text-blue-600">{formatCurrency(projectedSmallLeakageAfter)}</p><p className="mt-1 text-sm text-blue-700">Projected small-spend leakage</p></div>
            <div className="rounded-3xl bg-green-50 p-6"><p className="text-sm font-bold text-green-600">Total Estimated Savings</p><p className="mt-2 text-3xl font-black text-green-600">{formatCurrency(afterSaving)}</p><p className="mt-1 text-sm text-green-700">Small cuts, fees, duplicates, and subscriptions combined</p></div>
          </div>
          <p className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">Small-spend after-action assumes a 30% reduction in transactions below ₹500. Total estimated savings combines all recommendations, so it can differ from the small-spend-only number.</p>
        </SectionCard>
      </div>
    </AppLayout>
  );
}
