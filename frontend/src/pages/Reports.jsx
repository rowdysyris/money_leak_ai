import { useState } from "react";
import apiClient, { getFriendlyErrorMessage } from "../api/client";
import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import AppIcon from "../components/ui/AppIcon";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import { useToast } from "../components/ui/Toast";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatNumber } from "../utils/formatters";

const REPORTS = [
  { type: "pdf", title: "PDF Report", description: "Best for manager review. Includes summary, leaks, subscriptions, bill reminders, refund tracking, month-change explanations, and recommendations.", endpoint: "/api/reports/download/pdf", estimate: "1–3 MB", icon: "file" },
  { type: "csv", title: "CSV Transactions", description: "Best for audit/debugging. Includes cleaned transactions, categories, flags, confidence, and review fields.", endpoint: "/api/reports/download/csv", estimate: "100 KB–2 MB", icon: "receipt" },
  { type: "excel", title: "Excel Full Report", description: "Best for analysis. Includes transactions, category breakdown, subscriptions, bill reminders, refund tracking, month-change drivers, and priorities.", endpoint: "/api/reports/download/excel", estimate: "500 KB–5 MB", icon: "chart" }
];

/**
 * Render report download cards with analysis context.
 */
export default function Reports() {
  const [loadingType, setLoadingType] = useState("");
  const [error, setError] = useState("");
  const { showToast } = useToast();
  const summary = useApiResource("/api/dashboard/summary");
  const noStatement = !summary.loading && summary.data === null && (summary.warnings ?? []).some((warning) => String(warning).includes("No statement"));

  /**
   * Download a generated report from the backend.
   */
  async function handleDownload(report) {
    setLoadingType(report.type);
    setError("");
    try {
      const response = await apiClient.get(report.endpoint, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `moneyleak-${report.type}-report`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showToast({ type: "success", message: `${report.title} downloaded.` });
    } catch (requestError) {
      const message = getFriendlyErrorMessage(requestError);
      setError(message);
      showToast({ type: "error", message });
    } finally {
      setLoadingType("");
    }
  }

  if (summary.loading) {
    return <AppLayout title="Reports" subtitle="Download shareable, editable, and audit-ready financial reports."><SkeletonCard height="h-[420px]" /></AppLayout>;
  }

  if (noStatement) {
    return <AppLayout title="Reports" subtitle="Download shareable, editable, and audit-ready financial reports."><EmptyState icon="file" title="Upload a statement to generate reports" description="Reports become available after transaction analysis." actionLabel="Upload Statement" onAction={() => { window.location.href = "/upload"; }} /></AppLayout>;
  }

  return (
    <AppLayout title="Reports" subtitle="Download shareable, editable, and audit-ready financial reports.">
      <div className="space-y-6">
        {error || summary.error ? <ErrorBanner message={error || summary.error} onRetry={summary.refetch} /> : null}
        <SectionCard title="Report Context" subtitle="These numbers tell the reader what the report is based on before they download it.">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard label="Raw Total Spent" value={formatCurrency(summary.data?.total_spent_raw ?? summary.data?.total_spent)} color="text-red-500" />
              <MetricCard label="Actionable Spend" value={formatCurrency(summary.data?.total_spent_actionable ?? summary.data?.actionable_spend)} color="text-blue-600" />
              <MetricCard label="Review Transactions" value={formatNumber(summary.data?.uncategorized_transactions)} color="text-yellow-700" />
              <MetricCard label="Monthly Saving Possible" value={formatCurrency(summary.data?.possible_monthly_savings)} color="text-green-600" />
            </div>
        </SectionCard>

        <div className="grid gap-5 md:grid-cols-3">
          {REPORTS.map((report) => (
            <article key={report.type} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="icon-well grid h-12 w-12 place-items-center"><AppIcon name={report.icon} size={23} /></div>
              <h2 className="mt-4 text-2xl font-black text-slate-950">{report.title}</h2>
              <p className="mt-3 text-sm leading-6 text-slate-500">{report.description}</p>
              <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-xs font-bold text-slate-600">
                <p>Estimated size: {report.estimate}</p>
                <p className="mt-1">Format: {report.type.toUpperCase()}</p>
              </div>
              <button type="button" onClick={() => handleDownload(report)} disabled={loadingType === report.type} className="signal-button mt-6 w-full justify-center px-4 py-3 font-black text-white disabled:opacity-50">
                {loadingType === report.type ? "Downloading..." : "Download"}
              </button>
            </article>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
