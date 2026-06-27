import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import WarningBanner from "../components/ui/WarningBanner";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatDate, formatNumber, safeArray, toNumber } from "../utils/formatters";

/**
 * Return badge type for an alert priority or status.
 */
function badgeType(value) {
  const text = String(value ?? "").toLowerCase();
  if (["high", "overdue", "needs_review"].includes(text)) {
    return "high";
  }
  if (["medium", "due_soon", "upcoming"].includes(text)) {
    return "medium";
  }
  return "low";
}

/**
 * Return plain status label for reminder rows.
 */
function statusLabel(value) {
  const text = String(value ?? "watch").toLowerCase();
  if (text === "due_soon") {
    return "Due soon";
  }
  if (text === "needs_review") {
    return "Needs review";
  }
  return text.replace(/_/g, " ").replace(/^./, (letter) => letter.toUpperCase());
}

/**
 * Render bill and refund intelligence alerts.
 */
export default function SmartAlerts() {
  const alerts = useApiResource("/api/insights/smart-alerts", { initialData: { summary: {}, bill_reminders: {}, refund_tracking: {} } });
  const reminderSummary = alerts.data?.summary?.bill_reminders ?? alerts.data?.bill_reminders?.summary ?? {};
  const refundSummary = alerts.data?.summary?.refund_tracking ?? alerts.data?.refund_tracking?.summary ?? {};
  const reminders = safeArray(alerts.data?.bill_reminders?.reminders);
  const refundsReceived = safeArray(alerts.data?.refund_tracking?.refunds_received);
  const reviewItems = safeArray(alerts.data?.refund_tracking?.review_items);
  const actionCount = toNumber(alerts.data?.summary?.action_required_count);

  if (alerts.loading) {
    return <AppLayout title="Smart Alerts" subtitle="Bill reminders, refund tracking, and money-recovery checks."><SkeletonCard height="h-[520px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Smart Alerts" subtitle="Track upcoming bills, subscription renewals, refunds, reversals, failed payments, and chargebacks.">
      <div className="space-y-6">
        {alerts.error ? <ErrorBanner message={alerts.error} onRetry={alerts.refetch} /> : null}
        <WarningBanner warnings={alerts.warnings} />

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Action Required" value={formatNumber(actionCount)} subtitle="Overdue, due soon, or missing-refund checks" icon="alert" color={actionCount > 0 ? "text-red-600" : "text-green-700"} />
          <MetricCard label="Upcoming Bill Amount" value={formatCurrency(reminderSummary?.upcoming_amount)} subtitle="Due or expected within 30 days" icon="calendar" color="text-blue-600" />
          <MetricCard label="Refunds Received" value={formatCurrency(refundSummary?.refunds_received_amount)} subtitle={`${formatNumber(refundSummary?.refunds_received_count)} refund/reversal credits`} icon="refund" color="text-green-700" />
          <MetricCard label="Missing Refund Review" value={formatCurrency(refundSummary?.missing_refund_amount)} subtitle={`${formatNumber(refundSummary?.missing_refund_count)} possible missing reversals`} icon="receipt" color="text-red-600" />
        </div>

        <SectionCard title="Bill due-date and renewal reminders" subtitle="Predicted from subscriptions, rent, EMI, and fixed-payment patterns in your statement.">
          {reminders.length === 0 ? <EmptyState icon="calendar" title="No reminders detected" description="Upload more months to let the app learn recurring bill dates." /> : (
            <div className="grid gap-4 lg:grid-cols-2">
              {reminders.slice(0, 12).map((item) => (
                <article key={`${item.merchant}-${item.predicted_due_date}-${item.source}`} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-black text-slate-950">{item.merchant}</h2>
                      <p className="mt-1 text-sm font-semibold text-slate-500">{item.category} · {formatCurrency(item.amount)}</p>
                    </div>
                    <Badge label={statusLabel(item.status)} type={badgeType(item.status)} />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs font-bold text-slate-500">Last paid</p><p className="mt-1 font-black text-slate-950">{formatDate(item.last_paid_date)}</p></div>
                    <div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs font-bold text-slate-500">Predicted due</p><p className="mt-1 font-black text-slate-950">{formatDate(item.predicted_due_date)}</p></div>
                    <div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs font-bold text-slate-500">Priority</p><p className="mt-1 font-black capitalize text-slate-950">{item.priority}</p></div>
                  </div>
                  <p className="mt-4 text-sm font-semibold leading-6 text-slate-500">{item.reason}</p>
                </article>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="Refund, failed-payment, and reversal tracking" subtitle="Find credits that look like refunds and debits that may still need reversal review.">
          {reviewItems.length === 0 && refundsReceived.length === 0 ? <EmptyState icon="refund" title="No refund activity detected" description="The uploaded statement does not show refund/reversal patterns yet." /> : (
            <div className="space-y-5">
              {reviewItems.length ? (
                <div className="table-scroll overflow-x-auto rounded-3xl border border-slate-100">
                  <table className="min-w-[920px] w-full text-sm">
                    <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                      <tr><th className="px-4 py-3">Merchant</th><th className="px-4 py-3">Date</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Matched Refund</th><th className="px-4 py-3">Reason</th></tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {reviewItems.map((item, index) => (
                        <tr key={`${item.transaction_id}-${index}`} className="hover:bg-blue-50/40">
                          <td className="px-4 py-3 font-black text-slate-950">{item.merchant}</td>
                          <td className="px-4 py-3 font-semibold text-slate-600">{formatDate(item.transaction_date)}</td>
                          <td className="px-4 py-3 text-right font-black text-red-600">{formatCurrency(item.amount)}</td>
                          <td className="px-4 py-3"><Badge label={statusLabel(item.status)} type={badgeType(item.status)} /></td>
                          <td className="px-4 py-3 text-sm text-slate-600">{item.matched_refund_date ? `${formatCurrency(item.matched_refund_amount)} on ${formatDate(item.matched_refund_date)}` : "Not found"}</td>
                          <td className="px-4 py-3 text-slate-500">{item.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {refundsReceived.length ? (
                <div className="rounded-3xl bg-green-50 p-5">
                  <h3 className="font-black text-green-900">Refund credits detected</h3>
                  <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {refundsReceived.slice(0, 9).map((item, index) => (
                      <div key={`${item.transaction_id}-${index}`} className="rounded-2xl bg-white p-4 ring-1 ring-green-100">
                        <p className="font-black text-slate-950">{item.merchant}</p>
                        <p className="mt-1 text-sm text-slate-500">{formatDate(item.transaction_date)}</p>
                        <p className="mt-2 text-xl font-black text-green-700">{formatCurrency(item.amount)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </SectionCard>
      </div>
    </AppLayout>
  );
}
