import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import WarningBanner from "../components/ui/WarningBanner";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatNumber, formatPercent, getLeakScoreColor, getLeakScoreSeverity, safeArray, toNumber } from "../utils/formatters";

const PIE_COLORS = ["#2563EB", "#16A34A", "#F97316", "#A855F7", "#64748B"];

/**
 * Return chart legend rows with rich category labels.
 */
function CategoryLegend({ rows }) {
  if (!rows?.length) {
    return null;
  }
  const total = rows.reduce((sum, row) => sum + toNumber(row?.value), 0);
  return (
    <div className="mt-5 grid gap-2 text-sm">
      {rows.map((row, index) => {
        const pct = row?.percentage || ((toNumber(row?.value) / Math.max(total, 1)) * 100);
        return (
          <div key={row?.name ?? index} className="flex items-center justify-between gap-3 rounded-2xl bg-slate-50 px-3 py-2.5 ring-1 ring-slate-100">
            <span className="flex min-w-0 items-center gap-2 font-black text-slate-700">
              <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }} />
              <span className="truncate">{row?.name}</span>
            </span>
            <span className="shrink-0 text-right font-black text-slate-950">{formatCurrency(row?.value)} · {formatPercent(pct)}</span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Convert a category breakdown into top-four plus other chart data.
 */
function buildPieData(categories) {
  const rows = safeArray(categories);
  const topRows = rows.slice(0, 4);
  const otherAmount = rows.slice(4).reduce((sum, row) => sum + toNumber(row?.total_amount), 0);
  const chartRows = topRows.map((row) => ({ name: row?.category ?? "Unknown", value: toNumber(row?.total_amount), percentage: toNumber(row?.percentage_of_total_spend) }));
  if (otherAmount > 0) {
    chartRows.push({ name: "Others", value: otherAmount, percentage: 0 });
  }
  return chartRows;
}

/**
 * Render a custom pie-chart tooltip.
 */
function CategoryTooltip({ active, payload }) {
  if (!active || !payload?.length) {
    return null;
  }
  const item = payload[0]?.payload ?? {};
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-lg">
      <p className="text-sm font-black text-slate-950">{item?.name ?? "Category"}</p>
      <p className="text-sm text-slate-500">{formatCurrency(item?.value)} · {formatPercent(item?.percentage)}</p>
    </div>
  );
}

/**
 * Render a skeleton dashboard while multiple resources load.
 */
function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => <SkeletonCard key={index} height="h-32" />)}
      </div>
      <div className="grid gap-6 lg:grid-cols-2"><SkeletonCard height="h-96" /><SkeletonCard height="h-96" /></div>
    </div>
  );
}

/**
 * Render a needs/wants/waste composition bar.
 */
function SplitBar({ split }) {
  const needsPct = toNumber(split?.needs_pct);
  const wantsPct = toNumber(split?.wants_pct);
  const wastePct = toNumber(split?.waste_pct);
  const savingsActivity = toNumber(split?.savings_total);
  const savingsRate = toNumber(split?.savings_rate_pct ?? split?.savings_pct);
  return (
    <div>
      <div className="flex h-4 overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200">
        <div className="bg-blue-500" style={{ width: `${needsPct}%` }} />
        <div className="bg-purple-500" style={{ width: `${wantsPct}%` }} />
        <div className="bg-red-500" style={{ width: `${wastePct}%` }} />
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 text-xs font-black sm:grid-cols-3">
        <span className="rounded-full bg-blue-50 px-3 py-2 text-blue-700">Needs {formatPercent(needsPct)}</span>
        <span className="rounded-full bg-purple-50 px-3 py-2 text-purple-700">Wants {formatPercent(wantsPct)}</span>
        <span className="rounded-full bg-red-50 px-3 py-2 text-red-700">Waste {formatPercent(wastePct)}</span>
      </div>
      <div className="mt-4 rounded-3xl border border-green-100 bg-green-50 p-4 text-sm text-green-800">
        <p className="font-black">Savings activity</p>
        <p className="mt-1 leading-6">{formatCurrency(savingsActivity)} moved to investments/savings · {formatPercent(savingsRate)} of detected credits.</p>
      </div>
    </div>
  );
}

/**
 * Render a ranked merchant row.
 */
function MerchantRow({ merchant, index }) {
  return (
    <tr>
      <td className="px-4 py-3 font-black text-slate-500">#{index + 1}</td>
      <td className="px-4 py-3 font-black">{merchant?.merchant ?? "Unknown"}</td>
      <td className="px-4 py-3"><Badge label={merchant?.category ?? "Miscellaneous"} type="info" /></td>
      <td className="px-4 py-3 text-right font-black">{formatCurrency(merchant?.total_spent)}</td>
      <td className="px-4 py-3 text-right">{formatNumber(merchant?.transaction_count)}</td>
    </tr>
  );
}

/**
 * Render the main dashboard.
 */
export default function Dashboard() {
  const summary = useApiResource("/api/dashboard/summary");
  const categories = useApiResource("/api/dashboard/category-breakdown", { initialData: [] });
  const merchants = useApiResource("/api/dashboard/top-merchants", { initialData: [] });
  const split = useApiResource("/api/dashboard/needs-wants-waste");
  const survival = useApiResource("/api/insights/burn-rate");

  const resources = [summary, categories, merchants, split, survival];
  const loading = resources.some((resource) => resource.loading);
  const error = resources.find((resource) => resource.error)?.error ?? "";
  const allWarnings = resources.flatMap((resource) => resource.warnings ?? []);
  const summaryData = summary.data ?? null;
  const score = summaryData?.money_leak_score?.score ?? summaryData?.money_leak_score ?? 0;
  const chartData = buildPieData(categories.data);
  const savingRows = safeArray(summaryData?.saving_priority_list);
  const highValueRows = safeArray(summaryData?.high_value_review_transactions);
  const noStatement = !loading && summaryData === null && allWarnings.some((warning) => String(warning).includes("No statement"));
  const dailyBurn = toNumber(survival.data?.daily_burn_rate);
  const projection = toNumber(survival.data?.monthly_projection);

  if (loading) {
    return <AppLayout title="Dashboard" subtitle="Your spending diagnosis and saving opportunities."><DashboardSkeleton /></AppLayout>;
  }

  if (noStatement) {
    return (
      <AppLayout title="Dashboard" subtitle="Your spending diagnosis and saving opportunities.">
        <EmptyState icon="upload" title="Upload your bank statement to get started" description="Your dashboard appears after MoneyLeak AI processes a CSV or Excel statement." actionLabel="Upload Statement" onAction={() => { window.location.href = "/upload"; }} />
      </AppLayout>
    );
  }

  return (
    <AppLayout title="Dashboard" subtitle="Your spending diagnosis and saving opportunities.">
      <div className="space-y-6">
        {error ? <ErrorBanner message={error} onRetry={() => resources.forEach((resource) => resource.refetch())} /> : null}
        <WarningBanner warnings={allWarnings} />

        <section className="rounded-[2rem] bg-slate-950 p-5 text-white shadow-xl sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-black uppercase tracking-[0.25em] text-blue-300">Financial command center</p>
              <h2 className="mt-3 max-w-3xl text-2xl font-black tracking-tight sm:text-4xl">{summaryData?.money_leak_score?.diagnosis ?? "Your spending diagnosis is ready."}</h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">Actionable analytics exclude credits, transfers, cash withdrawals, investments, and manual-review anomalies.</p>
            </div>
            <div className={`w-fit rounded-2xl border px-4 py-3 text-sm font-black ${getLeakScoreColor(score)}`}>Score {formatNumber(score)} · {getLeakScoreSeverity(score)}</div>
          </div>
        </section>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Total Spent" value={formatCurrency(summaryData?.total_spent_raw ?? summaryData?.total_spent)} subtitle="Raw debits including review items" icon="spend" color="text-red-500" />
          <MetricCard label="Actionable Spend" value={formatCurrency(summaryData?.total_spent_actionable ?? summaryData?.actionable_spend)} subtitle="Used for diagnosis and savings" icon="target" color="text-blue-600" />
          <MetricCard label="Total Received" value={formatCurrency(summaryData?.total_received)} subtitle="Credits detected in statement" icon="income" color="text-green-600" />
          <MetricCard label="Net Balance" value={formatCurrency(summaryData?.net_balance_change)} subtitle="Raw money in minus money out" icon="scale" color="text-blue-600" />
          <MetricCard label="Money Leak Score" value={`${formatNumber(score)} · ${getLeakScoreSeverity(score)}`} subtitle="Lower score means healthier control" icon="alert" color={toNumber(score) > 60 ? "text-red-600" : "text-green-600"} />
          <MetricCard label="Monthly Savings Possible" value={formatCurrency(summaryData?.possible_monthly_savings)} subtitle="Capped to controllable spend" icon="check" color="text-green-600" />
          <MetricCard label="Top Category" value={summaryData?.top_spending_category ?? "—"} subtitle="Largest actionable category" icon="tag" color="text-slate-950" />
          <MetricCard label="Review Queue" value={`${highValueRows.length} flagged`} subtitle="High-value or anomalous items" icon="inspect" color="text-amber-600" />
        </div>

        {highValueRows.length > 0 ? (
          <SectionCard title="High-Value Transactions Needing Review" subtitle="These are excluded from actionable spend, category percentages, top merchants, savings estimates, and leak-score calculations.">
            <div className="table-scroll overflow-x-auto rounded-3xl border border-slate-100">
              <table className="min-w-[760px] w-full text-sm">
                <thead className="bg-amber-50 text-left text-xs uppercase text-amber-700"><tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Merchant</th><th className="px-4 py-3">Description</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Reason</th></tr></thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {highValueRows.map((row, index) => (
                    <tr key={`${row?.transaction_id ?? row?.merchant ?? "review"}-${index}`} className="bg-amber-50/30">
                      <td className="px-4 py-3 font-bold">{row?.date ?? "—"}</td>
                      <td className="px-4 py-3 font-black">{row?.merchant ?? "Unknown"}</td>
                      <td className="px-4 py-3 text-slate-600">{row?.description ?? "—"}</td>
                      <td className="px-4 py-3 text-right font-black text-amber-700">{formatCurrency(row?.amount)}</td>
                      <td className="px-4 py-3 text-slate-600">{row?.reason ?? "Needs review"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <SectionCard title="Spending by Category" subtitle="Top four categories plus others. Percentages use actionable spend.">
            {chartData.length === 0 ? <EmptyState icon="chart" title="No category data" description="Category breakdown appears after statement processing." /> : (
              <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
                <div className="relative h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={70} outerRadius={112} paddingAngle={3}>
                        {chartData.map((entry, index) => <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />)}
                      </Pie>
                      <Tooltip content={<CategoryTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
                    <div>
                      <p className="text-xs font-black uppercase tracking-wide text-slate-400">Actionable</p>
                      <p className="text-sm font-black text-slate-950">{formatCurrency(summaryData?.total_spent_actionable ?? summaryData?.actionable_spend)}</p>
                    </div>
                  </div>
                </div>
                <CategoryLegend rows={chartData} />
              </div>
            )}
          </SectionCard>

          <SectionCard title="Money Diagnosis" subtitle="Leak score and needs/wants/waste split.">
            <div className="rounded-[1.75rem] bg-slate-950 p-5 text-white shadow-inner">
              <p className="text-sm text-slate-400">Diagnosis</p>
              <p className="mt-3 text-2xl font-black leading-tight">{summaryData?.money_leak_score?.diagnosis ?? "No major leakage signal yet."}</p>
              <p className={`mt-5 inline-flex rounded-full border px-3 py-1 text-sm font-black ${getLeakScoreColor(score)}`}>{getLeakScoreSeverity(score)}</p>
            </div>
            <div className="mt-5"><SplitBar split={split.data ?? {}} /></div>
          </SectionCard>
        </div>

        <SectionCard title="Category Table">
          {safeArray(categories.data).length === 0 ? <EmptyState icon="tag" title="No categories yet" description="Upload transactions to see category analytics." /> : (
            <div className="table-scroll overflow-x-auto rounded-3xl border border-slate-100">
              <table className="min-w-[780px] w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Category</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3 text-right">Transactions</th><th className="px-4 py-3 text-right">% of Actionable Spend</th><th className="px-4 py-3 text-right">Avg.</th><th className="px-4 py-3">Type</th></tr></thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {safeArray(categories.data).map((row) => (
                    <tr key={row?.category ?? "unknown"}>
                      <td className="px-4 py-3 font-black">{row?.category ?? "Unknown"}</td>
                      <td className="px-4 py-3 text-right font-bold">{formatCurrency(row?.total_amount)}</td>
                      <td className="px-4 py-3 text-right">{formatNumber(row?.transaction_count)}</td>
                      <td className="px-4 py-3 text-right">{formatPercent(row?.percentage_of_total_spend)}</td>
                      <td className="px-4 py-3 text-right">{formatCurrency(row?.average_transaction_amount)}</td>
                      <td className="px-4 py-3"><Badge label={row?.need_want_waste_type ?? "unknown"} type={row?.need_want_waste_type ?? "unknown"} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <SectionCard title="What to Cut First">
            {savingRows.length === 0 ? <EmptyState icon="check" title="No recommendations yet" description="Saving opportunities appear once spending data exists." /> : (
              <div className="space-y-3">
                {savingRows.slice(0, 5).map((item, index) => (
                  <div key={`${item?.target ?? "target"}-${index}`} className="rounded-3xl border border-slate-200 bg-white p-4 transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-black text-blue-600">#{item?.rank ?? index + 1}</p>
                        <h3 className="mt-1 font-black text-slate-950">{item?.target ?? item?.target_category ?? "Saving opportunity"}</h3>
                        <p className="mt-1 text-sm leading-6 text-slate-500">{item?.reason ?? item?.action ?? "Reduce this category to save more."}</p>
                      </div>
                      <p className="shrink-0 rounded-2xl bg-green-50 px-3 py-2 text-sm font-black text-green-700">{formatCurrency(item?.possible_monthly_saving)} / month</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard title="Discretionary Burn Rate" subtitle="Calculated from actionable transactions in the dominant statement year, excluding date outliers, anomalies, transfers, cash withdrawals, and investments.">
            <div className="grid gap-4 sm:grid-cols-2">
              <MetricCard label="Daily Actionable Burn" value={formatCurrency(dailyBurn)} subtitle={dailyBurn > 0 ? "Average controllable daily outflow" : "Upload data to calculate"} color="text-red-500" />
              <MetricCard label="30-Day Projection" value={formatCurrency(projection)} subtitle="Estimated controllable monthly run-rate" color="text-blue-600" />
              <MetricCard label="Days Until Empty" value={survival.data?.days_until_empty ? formatNumber(survival.data?.days_until_empty) : "Add balance"} subtitle="Current balance needed for survival estimate" color="text-slate-950" />
              <MetricCard label="Daily Safe Limit" value={survival.data?.daily_safe_limit ? formatCurrency(survival.data?.daily_safe_limit) : "Add balance"} subtitle="Set balance to calculate safe daily spend" color="text-green-600" />
            </div>
          </SectionCard>
        </div>

        <SectionCard title="Top Merchants" subtitle="Highest actionable merchant spend after removing anomalies and review items.">
          {safeArray(merchants.data).length === 0 ? <EmptyState icon="store" title="No merchant data" description="Merchant analytics appears after transactions are processed." /> : (
            <div className="table-scroll overflow-x-auto rounded-3xl border border-slate-100">
              <table className="min-w-[720px] w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Rank</th><th className="px-4 py-3">Merchant</th><th className="px-4 py-3">Category</th><th className="px-4 py-3 text-right">Total Spent</th><th className="px-4 py-3 text-right">Transactions</th></tr></thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {safeArray(merchants.data).slice(0, 10).map((merchant, index) => <MerchantRow key={merchant?.merchant ?? index} merchant={merchant} index={index} />)}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </AppLayout>
  );
}
