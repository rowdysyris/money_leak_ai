/**
 * Render a consistent premium content surface.
 */
export default function SectionCard({ title, subtitle, action, children, className = "" }) {
  return (
    <section className={`section-panel p-5 sm:p-6 ${className}`}>
      {(title || subtitle || action) ? (
        <div className="section-panel__header mb-5 flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            {title ? <h2 className="text-lg font-extrabold text-slate-950">{title}</h2> : null}
            {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{subtitle}</p> : null}
          </div>
          {action ?? null}
        </div>
      ) : null}
      {children}
    </section>
  );
}
