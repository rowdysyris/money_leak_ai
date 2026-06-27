import { useMemo, useState } from "react";
import { formatCurrency } from "../../utils/formatters";

/**
 * Format raw warning text into concise user-facing copy.
 */
function normalizeWarning(warning) {
  const text = String(warning ?? "").trim();
  if (!text) {
    return "";
  }
  let formatted = text.replace(/₹(\d+(?:\.\d+)?)/g, (_match, amount) => formatCurrency(Number(amount)));
  if (formatted.includes("high-value transaction(s) totaling")) {
    return formatted.replace("were excluded from actionable dashboard analytics and need review", "were excluded from actionable analytics and need review");
  }
  if (formatted.includes("high-value or anomalous transactions were excluded from savings projections")) {
    return formatted.replace("and should be reviewed separately", "");
  }
  return formatted;
}

/**
 * Return unique warning messages with repeat counts.
 */
function groupWarnings(warnings) {
  const counts = new Map();
  (Array.isArray(warnings) ? warnings : []).forEach((warning) => {
    const normalized = normalizeWarning(warning);
    if (!normalized) {
      return;
    }
    counts.set(normalized, (counts.get(normalized) ?? 0) + 1);
  });
  return Array.from(counts.entries()).map(([message, count]) => ({ message, count }));
}

/**
 * Render a collapsible list of API warnings without duplicate noise.
 */
export default function WarningBanner({ warnings = [] }) {
  const [open, setOpen] = useState(false);
  const visibleWarnings = useMemo(() => groupWarnings(warnings), [warnings]);
  if (visibleWarnings.length === 0) {
    return null;
  }
  return (
    <div className="rounded-2xl border border-yellow-200 bg-yellow-50 p-4 text-yellow-800">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between text-left text-sm font-semibold">
        <span>{visibleWarnings.length} warning group{visibleWarnings.length === 1 ? "" : "s"}</span>
        <span>{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
          {visibleWarnings.map((warning) => (
            <li key={warning.message}>{warning.message}{warning.count > 1 ? ` · repeated ${warning.count}×` : ""}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
