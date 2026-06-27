import { useMemo, useState } from "react";
import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import AppIcon from "../components/ui/AppIcon";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatDate, formatPercent, safeArray, toNumber } from "../utils/formatters";

/**
 * Convert a backend subscription frequency into user-facing text.
 */
function frequencyLabel(frequency) {
  const normalized = String(frequency ?? "irregular").toLowerCase();
  if (normalized === "irregular") {
    return "Potential recurring";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

/**
 * Convert a backend confidence score into a short badge label.
 */
function confidenceLabel(confidenceScore) {
  const confidence = toNumber(confidenceScore);
  if (confidence >= 0.8) {
    return "High confidence";
  }
  if (confidence >= 0.6) {
    return "Medium confidence";
  }
  return "Low confidence";
}

/**
 * Convert a backend confidence score into Badge color type.
 */
function confidenceType(confidenceScore) {
  const confidence = toNumber(confidenceScore);
  if (confidence >= 0.8) {
    return "low";
  }
  if (confidence >= 0.6) {
    return "medium";
  }
  return "high";
}

/**
 * Explain why a cancellation priority was assigned.
 */
function priorityReason(priority, yearlyCost) {
  const cost = toNumber(yearlyCost);
  const value = String(priority ?? "low").toLowerCase();
  if (value === "high") {
    return `High priority because annual cost is ${formatCurrency(cost)}, above the ₹6,000 threshold.`;
  }
  if (value === "medium") {
    return `Medium priority because annual cost is ${formatCurrency(cost)}, above the ₹1,500 threshold.`;
  }
  return "Low priority because the annual impact is relatively small.";
}

/**
 * Label predicted dates safely.
 */
function predictionLabel(subscription) {
  if (!subscription?.next_predicted_date) {
    return "Not enough pattern";
  }
  const predicted = new Date(subscription.next_predicted_date);
  const today = new Date();
  const prefix = !Number.isNaN(predicted.getTime()) && predicted < today ? "Expected around" : "Next predicted";
  return `${prefix} ${formatDate(subscription.next_predicted_date)}`;
}

/**
 * Render a compact subscription card.
 */
function SubscriptionCard({ subscription }) {
  const isIrregular = String(subscription?.frequency ?? "irregular").toLowerCase() === "irregular";
  return (
    <article className="rounded-[1.75rem] border border-white/80 bg-white/90 p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="break-words text-xl font-black leading-tight text-slate-950">{subscription?.merchant ?? "Unknown"}</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge label={frequencyLabel(subscription?.frequency)} type={isIrregular ? "medium" : "unknown"} />
            <Badge label={confidenceLabel(subscription?.confidence_score)} type={confidenceType(subscription?.confidence_score)} />
            {subscription?.confidence_score !== undefined ? <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-500">{formatPercent(toNumber(subscription?.confidence_score) * 100)}</span> : null}
          </div>
        </div>
        <span className="icon-well grid h-11 w-11 shrink-0 place-items-center"><AppIcon name="repeat" size={20} /></span>
      </div>

      {isIrregular ? <p className="mt-4 rounded-2xl bg-yellow-50 p-3 text-sm font-semibold leading-6 text-yellow-800">Pattern is not consistent enough. Review recent charges before cancelling because this may be a one-time payment or inconsistent plan.</p> : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs font-bold text-slate-500">Monthly</p><p className="text-2xl font-black text-slate-950">{formatCurrency(subscription?.monthly_cost)}</p></div>
        <div className="rounded-2xl bg-red-50 p-3"><p className="text-xs font-bold text-red-500">Yearly</p><p className="text-2xl font-black text-red-500">{formatCurrency(subscription?.yearly_cost)}</p></div>
      </div>

      <div className="mt-4 grid gap-2 text-sm">
        <div className="flex items-center justify-between gap-3"><span className="text-slate-500">Last charge</span><span className="font-black">{formatDate(subscription?.last_charge_date)}</span></div>
        <div className="flex items-center justify-between gap-3"><span className="text-slate-500">Prediction</span><span className="text-right font-black">{predictionLabel(subscription)}</span></div>
      </div>

      <div className="mt-4 rounded-2xl bg-slate-50 p-3">
        <Badge label={`${subscription?.cancellation_priority ?? "low"} priority`} type={subscription?.cancellation_priority ?? "low"} />
        <p className="mt-2 text-xs font-semibold leading-5 text-slate-500">{priorityReason(subscription?.cancellation_priority, subscription?.yearly_cost)}</p>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <button type="button" onClick={() => { window.location.href = "/transactions"; }} className="rounded-full border border-slate-200 px-3 py-2 text-xs font-black hover:bg-slate-50">Review in Transactions</button>
        <button type="button" className="rounded-full border border-slate-200 px-3 py-2 text-xs font-black hover:bg-slate-50">Not a subscription</button>
      </div>
    </article>
  );
}

/**
 * Render detected subscriptions.
 */
export default function Subscriptions() {
  const [sortBy, setSortBy] = useState("yearly_cost");
  const resource = useApiResource("/api/insights/subscriptions", { initialData: [] });
  const subscriptions = useMemo(function sortSubscriptions() {
    return [...safeArray(resource.data)].sort((a, b) => {
      if (sortBy === "priority") {
        const priority = { high: 3, medium: 2, low: 1 };
        return (priority[b?.cancellation_priority] ?? 0) - (priority[a?.cancellation_priority] ?? 0);
      }
      return toNumber(b?.yearly_cost) - toNumber(a?.yearly_cost);
    });
  }, [resource.data, sortBy]);
  const confirmedSubscriptions = subscriptions.filter((item) => String(item?.frequency ?? "irregular").toLowerCase() !== "irregular");
  const potentialSubscriptions = subscriptions.filter((item) => String(item?.frequency ?? "irregular").toLowerCase() === "irregular");
  const confirmedMonthly = confirmedSubscriptions.reduce((sum, item) => sum + toNumber(item?.monthly_cost), 0);
  const potentialMonthly = potentialSubscriptions.reduce((sum, item) => sum + toNumber(item?.monthly_cost), 0);
  const totalYearly = subscriptions.reduce((sum, item) => sum + toNumber(item?.yearly_cost), 0);
  const highPriorityCount = subscriptions.filter((item) => item?.cancellation_priority === "high").length;

  if (resource.loading) {
    return <AppLayout title="Subscriptions" subtitle="Detected recurring payments and cancellation priorities."><SkeletonCard height="h-[540px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Subscriptions" subtitle="Detected recurring payments and cancellation priorities.">
      <div className="space-y-6">
        {resource.error ? <ErrorBanner message={resource.error} onRetry={resource.refetch} /> : null}

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="rounded-[2rem] bg-slate-950 p-5 text-white shadow-xl lg:flex-1">
            <p className="text-sm font-black uppercase tracking-[0.25em] text-blue-300">Recurring spend control</p>
            <h2 className="mt-3 text-3xl font-black">{formatCurrency(totalYearly)} annual subscription exposure</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">Confirmed and potential recurring charges are separated so you do not cancel one-time payments by mistake.</p>
          </div>
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold shadow-sm">
            <option value="yearly_cost">Sort by Yearly Cost</option>
            <option value="priority">Sort by Cancellation Priority</option>
          </select>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Confirmed Monthly" value={formatCurrency(confirmedMonthly)} subtitle="Stable recurring payments" icon="check" color="text-slate-950" />
          <MetricCard label="Potential Monthly" value={formatCurrency(potentialMonthly)} subtitle="Needs manual confirmation" icon="pending" color="text-yellow-700" />
          <MetricCard label="Yearly Subscription Cost" value={formatCurrency(totalYearly)} subtitle="Confirmed + potential" icon="calendar" color="text-red-500" />
          <MetricCard label="High Priority Items" value={highPriorityCount} subtitle="Above ₹6,000/year" icon="alert" color="text-red-500" />
        </div>

        {subscriptions.length === 0 ? <EmptyState icon="package" title="No subscriptions detected" description="Recurring weekly, monthly, quarterly, and yearly payments will appear here." /> : (
          <div className="space-y-8">
            {[{ title: "Confirmed recurring", subtitle: "High-confidence charges with recurring intervals.", rows: confirmedSubscriptions }, { title: "Potential recurring", subtitle: "Known subscription merchants with weak or inconsistent payment patterns.", rows: potentialSubscriptions }].map((group) => group.rows.length > 0 ? (
              <SectionCard key={group.title} title={group.title} subtitle={group.subtitle}>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {group.rows.map((subscription, index) => <SubscriptionCard key={`${subscription?.merchant}-${index}`} subscription={subscription} />)}
                </div>
              </SectionCard>
            ) : null)}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
