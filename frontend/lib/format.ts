/** Compact "time ago" label, e.g. "just now", "3m ago", "2h ago", "5d ago". */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  // Backend timestamps are UTC; if the string carries no zone, treat it as UTC
  // so the browser doesn't parse it as local time and skew the result.
  const hasZone = /[zZ]|[+-]\d\d:?\d\d$/.test(iso);
  const then = new Date(hasZone ? iso : `${iso}Z`).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 45) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.round(months / 12)}y ago`;
}
