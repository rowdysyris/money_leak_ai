/**
 * Render an animated skeleton block.
 */
export default function SkeletonCard({ className = "", height = "h-32", width = "w-full" }) {
  return <div data-testid="skeleton-card" className={`${height} ${width} animate-pulse rounded-3xl bg-slate-200 ${className}`} />;
}
