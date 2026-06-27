/**
 * Convert any value into a finite number.
 */
export function toNumber(value) {
  const numberValue = Number(value ?? 0);
  return Number.isFinite(numberValue) ? numberValue : 0;
}

/**
 * Format money using Indian currency grouping.
 */
export function formatCurrency(amount) {
  const value = toNumber(amount);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: value % 1 === 0 ? 0 : 2
  }).format(value);
}

/**
 * Format a date as day month year.
 */
export function formatDate(dateString) {
  if (!dateString) {
    return "-";
  }
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(date);
}

/**
 * Format a numeric percentage.
 */
export function formatPercent(value) {
  const numberValue = toNumber(value);
  return `${Number.isInteger(numberValue) ? numberValue.toFixed(0) : numberValue.toFixed(1)}%`;
}

/**
 * Format a normal number using Indian grouping.
 */
export function formatNumber(n) {
  return new Intl.NumberFormat("en-IN").format(toNumber(n));
}

/**
 * Return Tailwind text/background classes for a leak score.
 */
export function getLeakScoreColor(score) {
  const value = toNumber(score);
  if (value < 30) {
    return "bg-green-100 text-green-700 border-green-200";
  }
  if (value <= 60) {
    return "bg-yellow-100 text-yellow-700 border-yellow-200";
  }
  return "bg-red-100 text-red-700 border-red-200";
}

/**
 * Return the severity label for a leak score.
 */
export function getLeakScoreSeverity(score) {
  const value = toNumber(score);
  if (value <= 30) {
    return "Healthy";
  }
  if (value <= 60) {
    return "Leaking";
  }
  if (value <= 80) {
    return "High Risk";
  }
  return "Critical";
}

/**
 * Convert API envelopes into safe arrays.
 */
export function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

/**
 * Convert API values into readable text.
 */
export function safeText(value, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}
