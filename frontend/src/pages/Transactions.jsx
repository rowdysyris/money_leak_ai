import { useMemo, useState } from "react";
import apiClient, { getFriendlyErrorMessage } from "../api/client";
import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import Badge from "../components/ui/Badge";
import AppIcon from "../components/ui/AppIcon";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import { useToast } from "../components/ui/Toast";
import { CATEGORIES } from "../constants/categories";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatDate, formatNumber, formatPercent, safeArray, toNumber } from "../utils/formatters";

const PAGE_SIZE = 50;

/**
 * Return a visual class for confidence values.
 */
function confidenceClass(confidence) {
  const value = toNumber(confidence);
  if (value > 0.8) {
    return "bg-green-500";
  }
  if (value >= 0.5) {
    return "bg-yellow-500";
  }
  return "bg-red-500";
}

/**
 * Return merchant text suitable for users.
 */
function displayMerchant(value) {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "unknown") {
    return "Unidentified merchant";
  }
  return text;
}

/**
 * Return description text with a readable fallback.
 */
function displayDescription(value) {
  const text = String(value ?? "").trim();
  return text || "Description unavailable";
}

/**
 * Render transaction flag chips.
 */
function Flags({ transaction }) {
  const flags = [
    transaction?.is_subscription ? ["package", "Sub"] : null,
    transaction?.is_duplicate ? ["warning", "Dup"] : null,
    transaction?.is_small_spend ? ["coins", "Small"] : null,
    transaction?.is_refund ? ["refund", "Refund"] : null,
    transaction?.needs_review ? ["help", "Review"] : null
  ].filter(Boolean);
  if (flags.length === 0) {
    return <span className="text-xs text-slate-400">—</span>;
  }
  return <div className="flex flex-wrap gap-1">{flags.map(([icon, label]) => <span key={`${icon}-${label}`} className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-700"><AppIcon name={icon} size={12} /> {label}</span>)}</div>;
}

/**
 * Render the transactions review table.
 */
export default function Transactions() {
  const [category, setCategory] = useState("All");
  const [type, setType] = useState("All");
  const [flag, setFlag] = useState("All");
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(0);
  const [showFilters, setShowFilters] = useState(true);
  const { showToast } = useToast();
  const resource = useApiResource("/api/transactions?limit=5000", { initialData: [] });
  const rows = safeArray(resource.data?.transactions ?? resource.data);
  const totalCount = toNumber(resource.data?.total ?? rows.length);
  const returnedCount = toNumber(resource.data?.returned ?? rows.length);

  const filteredRows = useMemo(function filterRows() {
    return rows.filter((row) => {
      const matchesCategory = category === "All" || row?.category === category;
      const matchesType = type === "All" || String(row?.transaction_type ?? "").toLowerCase() === type.toLowerCase();
      const haystack = `${row?.merchant ?? ""} ${row?.description ?? ""}`.toLowerCase();
      const matchesSearch = !search || haystack.includes(search.toLowerCase());
      const matchesFlag = flag === "All" || Boolean(row?.[flag]);
      const rowDate = String(row?.transaction_date ?? "").slice(0, 10);
      const matchesStartDate = !startDate || (rowDate && rowDate >= startDate);
      const matchesEndDate = !endDate || (rowDate && rowDate <= endDate);
      return matchesCategory && matchesType && matchesSearch && matchesFlag && matchesStartDate && matchesEndDate;
    });
  }, [rows, category, type, flag, search, startDate, endDate]);

  function resetFilters() {
    setCategory("All");
    setType("All");
    setFlag("All");
    setSearch("");
    setStartDate("");
    setEndDate("");
    setPage(0);
  }

  const pagedRows = filteredRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const reviewRows = rows.filter((row) => row?.needs_review);
  const reviewCount = reviewRows.length;
  const reviewSummary = {
    lowConfidence: reviewRows.filter((row) => toNumber(row?.category_confidence) < 0.5).length,
    unidentified: reviewRows.filter((row) => String(row?.merchant ?? "").trim().toLowerCase() === "unknown" || !String(row?.merchant ?? "").trim()).length,
    anomalies: reviewRows.filter((row) => row?.is_anomaly).length,
    futureDates: reviewRows.filter((row) => String(row?.description ?? "").toLowerCase().includes("future date")).length,
    transfers: reviewRows.filter((row) => row?.category === "Transfers").length
  };

  /**
   * Correct a transaction category through the backend.
   */
  async function handleCategoryChange(transactionId, nextCategory) {
    try {
      await apiClient.patch(`/api/transactions/${transactionId}/category`, { category: nextCategory });
      resource.setData((previous) => {
        const previousRows = safeArray(previous?.transactions ?? previous);
        const updatedRows = previousRows.map((row) => row?.id === transactionId ? { ...row, category: nextCategory, category_confidence: 1, category_source: "user_rule", needs_review: false } : row);
        return previous?.transactions ? { ...previous, transactions: updatedRows } : updatedRows;
      });
      showToast({ type: "success", message: "Category updated." });
    } catch (error) {
      showToast({ type: "error", message: getFriendlyErrorMessage(error) });
    }
  }

  if (resource.loading) {
    return <AppLayout title="Transactions" subtitle="Review, search, filter, and correct transaction categories."><SkeletonCard height="h-[520px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Transactions" subtitle="Review, search, filter, and correct transaction categories.">
      <div className="space-y-5">
        {resource.error ? <ErrorBanner message={resource.error} onRetry={resource.refetch} /> : null}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Total Transactions" value={formatNumber(totalCount)} subtitle={`${returnedCount} loaded`} icon="receipt" color="text-slate-950" />
          <MetricCard label="Needs Review" value={formatNumber(reviewCount)} subtitle="Manual checks recommended" icon="inspect" color="text-amber-600" />
          <MetricCard label="Low Confidence" value={formatNumber(reviewSummary.lowConfidence)} subtitle="Category confidence below 50%" icon="trend-down" color="text-red-500" />
          <MetricCard label="Unidentified" value={formatNumber(reviewSummary.unidentified)} subtitle="Merchant name unclear" icon="help" color="text-purple-600" />
          <MetricCard label="Transfer Review" value={formatNumber(reviewSummary.transfers)} subtitle="UPI/NEFT/IMPS checks" icon="transfer" color="text-blue-600" />
        </div>

        {reviewCount > 0 ? (
          <div className="rounded-[2rem] border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-900 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="font-black">Review Queue · {reviewCount} transactions need your review</p>
                <p className="mt-1 text-xs font-semibold text-yellow-800">Start with date anomalies and low-confidence unidentified merchants.</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-white px-3 py-1 text-xs font-black">Low confidence {reviewSummary.lowConfidence}</span>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-black">Unidentified {reviewSummary.unidentified}</span>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-black">Transfer review {reviewSummary.transfers}</span>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-black">Date/anomaly {reviewSummary.futureDates + reviewSummary.anomalies}</span>
                <button type="button" onClick={() => setFlag("needs_review")} className="rounded-full bg-yellow-500 px-4 py-2 text-xs font-black text-white shadow-sm">Show review rows</button>
              </div>
            </div>
          </div>
        ) : null}

        <SectionCard title="Filters" action={<button type="button" onClick={() => setShowFilters((value) => !value)} className="rounded-full border border-slate-200 px-4 py-2 text-xs font-black text-slate-600">{showFilters ? "Collapse" : "Expand"}</button>}>
          {showFilters ? (
            <div className="grid gap-3 xl:grid-cols-12">
              <label className="text-xs font-bold text-slate-500 xl:col-span-4">Search
                <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="Search merchant or description" className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500" />
              </label>
              <label className="text-xs font-bold text-slate-500 xl:col-span-2">Category
                <select value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }} className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm">
                  <option>All</option>{CATEGORIES.map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
              <label className="text-xs font-bold text-slate-500 xl:col-span-2">Type
                <select value={type} onChange={(event) => { setType(event.target.value); setPage(0); }} className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"><option>All</option><option>Debit</option><option>Credit</option></select>
              </label>
              <label className="text-xs font-bold text-slate-500 xl:col-span-2">Flags
                <select value={flag} onChange={(event) => { setFlag(event.target.value); setPage(0); }} className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm">
                  <option value="All">All Flags</option>
                  <option value="is_subscription">Subscriptions</option>
                  <option value="is_duplicate">Duplicates</option>
                  <option value="is_small_spend">Small Spend</option>
                  <option value="is_refund">Refunds</option>
                  <option value="needs_review">Needs Review</option>
                </select>
              </label>
              <div className="grid gap-3 sm:grid-cols-2 xl:col-span-2">
                <label className="text-xs font-bold text-slate-500">Start date
                  <input type="date" aria-label="Start date" title="Start date" value={startDate} onChange={(event) => { setStartDate(event.target.value); setPage(0); }} className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm" />
                  <span className="mt-1 block text-[11px] font-semibold text-slate-400">Use dd/mm/yyyy calendar picker</span>
                </label>
                <label className="text-xs font-bold text-slate-500">End date
                  <input type="date" aria-label="End date" title="End date" value={endDate} onChange={(event) => { setEndDate(event.target.value); setPage(0); }} className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm" />
                  <span className="mt-1 block text-[11px] font-semibold text-slate-400">Use dd/mm/yyyy calendar picker</span>
                </label>
              </div>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Transaction Table" subtitle={`${filteredRows.length} matching transactions · ${returnedCount} loaded of ${totalCount} total`} action={<div className="flex gap-2 text-xs font-bold text-slate-500"><span className="rounded-full bg-red-50 px-2 py-1 text-red-600">Red low</span><span className="rounded-full bg-yellow-50 px-2 py-1 text-yellow-700">Yellow medium</span><span className="rounded-full bg-green-50 px-2 py-1 text-green-700">Green high</span></div>}>
          {rows.length === 0 ? <EmptyState icon="receipt" title="Upload your bank statement to get started" description="Transactions will appear here after upload." actionLabel="Upload Statement" onAction={() => { window.location.href = "/upload"; }} /> : filteredRows.length === 0 ? <EmptyState icon="inspect" title="No transactions found" description="No rows match the current search and filters." actionLabel="Reset filters" onAction={resetFilters} /> : (
            <div className="table-scroll max-h-[760px] overflow-auto rounded-3xl border border-slate-100">
              <table className="min-w-[1120px] w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-3 py-3">Date</th><th className="px-3 py-3">Merchant</th><th className="px-3 py-3">Description</th><th className="px-3 py-3 text-right">Amount</th><th className="px-3 py-3">Type</th><th className="px-3 py-3">Category</th><th className="px-3 py-3">Confidence</th><th className="px-3 py-3">Flags</th></tr></thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {pagedRows.map((row) => (
                    <tr key={row?.id ?? `${row?.merchant}-${row?.transaction_date}`} className={row?.is_anomaly || String(row?.description ?? "").toLowerCase().includes("future date") ? "bg-amber-50/60" : ""}>
                      <td className="px-3 py-3 font-medium">{formatDate(row?.transaction_date)}</td>
                      <td className="px-3 py-3 font-black text-slate-950">{displayMerchant(row?.merchant)}</td>
                      <td className="max-w-xs px-3 py-3 text-slate-500"><span className="line-clamp-2">{displayDescription(row?.description)}</span></td>
                      <td className={`px-3 py-3 text-right font-black tabular-nums ${row?.transaction_type === "credit" ? "text-green-600" : "text-red-500"}`}>{formatCurrency(row?.amount)}</td>
                      <td className="px-3 py-3"><Badge label={row?.transaction_type ?? "unknown"} type={row?.transaction_type ?? "unknown"} /></td>
                      <td className="px-3 py-3">
                        {row?.needs_review ? (
                          <select aria-label={`Category for ${row?.merchant ?? "transaction"}`} value={row?.category ?? "Miscellaneous"} onChange={(event) => handleCategoryChange(row?.id, event.target.value)} className="w-44 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold">
                            {CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}
                          </select>
                        ) : <Badge label={row?.category ?? "Miscellaneous"} type="info" />}
                      </td>
                      <td className="px-3 py-3">
                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100"><div className={`h-full ${confidenceClass(row?.category_confidence)}`} style={{ width: `${Math.min(100, Math.max(0, toNumber(row?.category_confidence) * 100))}%` }} /></div>
                        <p className="mt-1 text-xs font-bold text-slate-500">{formatPercent(toNumber(row?.category_confidence) * 100)}</p>
                      </td>
                      <td className="px-3 py-3"><Flags transaction={row} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 flex items-center justify-between">
            <button type="button" onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} className="rounded-full border border-slate-200 px-4 py-2 text-sm font-bold disabled:opacity-40">Previous</button>
            <p className="text-sm font-bold text-slate-500">Page {page + 1}</p>
            <button type="button" onClick={() => setPage(page + 1)} disabled={(page + 1) * PAGE_SIZE >= filteredRows.length} className="rounded-full border border-slate-200 px-4 py-2 text-sm font-bold disabled:opacity-40">Next</button>
          </div>
        </SectionCard>
      </div>
    </AppLayout>
  );
}
