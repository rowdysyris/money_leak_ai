const TYPE_CLASSES = {
  need: "bg-blue-50 text-blue-700 border-blue-100",
  want: "bg-purple-50 text-purple-700 border-purple-100",
  waste: "bg-red-50 text-red-700 border-red-100",
  savings: "bg-green-50 text-green-700 border-green-100",
  debit: "bg-red-50 text-red-700 border-red-100",
  credit: "bg-green-50 text-green-700 border-green-100",
  high: "bg-red-50 text-red-700 border-red-100",
  medium: "bg-yellow-50 text-yellow-700 border-yellow-100",
  low: "bg-green-50 text-green-700 border-green-100",
  unknown: "bg-slate-50 text-slate-600 border-slate-100"
};

/**
 * Render a colored pill label.
 */
export default function Badge({ label, type = "unknown" }) {
  const classes = TYPE_CLASSES[String(type ?? "unknown").toLowerCase()] ?? TYPE_CLASSES.unknown;
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold ${classes}`}>{label ?? "Unknown"}</span>;
}
