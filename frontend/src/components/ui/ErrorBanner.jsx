/**
 * Render a user-safe error banner.
 */
export default function ErrorBanner({ message = "Something went wrong. Please try again.", onRetry }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm font-semibold">{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700">
          Retry
        </button>
      ) : null}
    </div>
  );
}
