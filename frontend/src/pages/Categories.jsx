import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import SkeletonCard from "../components/ui/SkeletonCard";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatPercent, safeArray } from "../utils/formatters";

/**
 * Render category analytics as a focused page.
 */
export default function Categories() {
  const resource = useApiResource("/api/dashboard/category-breakdown", { initialData: [] });
  const rows = safeArray(resource.data);

  if (resource.loading) {
    return <AppLayout title="Categories" subtitle="Understand your needs, wants, waste, and savings categories."><SkeletonCard height="h-[520px]" /></AppLayout>;
  }

  return (
    <AppLayout title="Categories" subtitle="Understand your needs, wants, waste, and savings categories.">
      {resource.error ? <ErrorBanner message={resource.error} onRetry={resource.refetch} /> : null}
      <SectionCard title="Category Breakdown">
        {rows.length === 0 ? <EmptyState icon="tag" title="No category data yet" description="Upload a statement to populate category analytics." actionLabel="Upload Statement" onAction={() => { window.location.href = "/upload"; }} /> : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((row) => (
              <article key={row?.category} className="rounded-3xl border border-slate-200 p-5">
                <div className="flex items-start justify-between gap-3"><h2 className="text-xl font-black text-slate-950">{row?.category ?? "Unknown"}</h2><Badge label={row?.need_want_waste_type ?? "unknown"} type={row?.need_want_waste_type ?? "unknown"} /></div>
                <p className="mt-4 text-3xl font-black text-blue-600">{formatCurrency(row?.total_amount)}</p>
                <p className="mt-2 text-sm text-slate-500">{row?.transaction_count ?? 0} transactions · {formatPercent(row?.percentage_of_total_spend)} of spend</p>
              </article>
            ))}
          </div>
        )}
      </SectionCard>
    </AppLayout>
  );
}
