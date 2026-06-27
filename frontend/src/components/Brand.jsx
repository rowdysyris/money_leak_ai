/** Render the supplied MoneyLeak AI brand artwork. */
export default function Brand({ className = "", compact = false }) {
  return (
    <span className={`brand-lockup ${compact ? "brand-lockup--compact" : ""} ${className}`}>
      <img src="/moneyleak-ai-logo.png" alt="MoneyLeak AI" />
    </span>
  );
}
