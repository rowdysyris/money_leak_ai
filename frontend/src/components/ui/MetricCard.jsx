/**
 * Render a premium metric with safe wrapping for large values.
 */
export default function MetricCard({ label, value, subtitle, color = "text-blue-600", icon, tone = "default" }) {
  const toneClass = tone === "dark"
    ? "border-slate-800 bg-slate-950 text-white"
    : "border-white/80 bg-white/90 text-slate-950";
  return (
    <section className={`metric-panel group relative overflow-hidden border p-5 transition ${toneClass}`}>
      <div className="metric-panel__signal absolute bottom-0 left-0 top-0 w-1" />
      <div className="flex items-start justify-between gap-3">
        <p className={`text-sm font-bold leading-5 ${tone === "dark" ? "text-slate-300" : "text-slate-500"}`}>{label ?? "Metric"}</p>
        {icon ? <span className="icon-well grid h-10 w-10 shrink-0 place-items-center"><AppIcon name={icon} size={19} /></span> : null}
      </div>
      <p className={`mt-4 break-words text-[1.7rem] font-black leading-tight sm:text-3xl ${color}`}>{value ?? "-"}</p>
      {subtitle ? <p className={`mt-2 text-xs font-semibold leading-5 ${tone === "dark" ? "text-slate-400" : "text-slate-500"}`}>{subtitle}</p> : null}
    </section>
  );
}
import AppIcon from "./AppIcon";
