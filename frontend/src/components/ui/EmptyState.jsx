/**
 * Render a reusable empty state with an optional action.
 */
export default function EmptyState({ icon = "file", title, description, actionLabel, onAction }) {
  return (
    <div className="empty-panel border border-dashed border-slate-300 bg-white p-8 text-center">
      <div className="icon-well mx-auto mb-4 flex h-14 w-14 items-center justify-center"><AppIcon name={icon} size={24} /></div>
      <h3 className="text-lg font-bold text-slate-950">{title ?? "Nothing to show"}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{description ?? "Data will appear here once available."}</p>
      {actionLabel ? (
        <button type="button" onClick={onAction} className="signal-button mt-5 px-5 py-2.5 text-sm font-semibold text-white">
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
import AppIcon from "./AppIcon";
