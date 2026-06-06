/**
 * Backend stores UTC as naive datetimes; JSON often has no `Z`. Without a zone,
 * `YYYY-MM-DDTHH:mm:ss` is treated as *local* wall time in JS, which breaks
 * `formatDistanceToNow` and `toLocaleString` vs the real instant.
 */
export function parseApiUtc(iso: string | null | undefined): Date {
  if (iso == null || iso === '') return new Date(NaN)
  const s = String(iso).trim()
  if (/Z$/i.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s)
  const t = s.includes('T') ? s : s.replace(' ', 'T')
  if (/^\d{4}-\d{2}-\d{2}T/.test(t)) return new Date(`${t}Z`)
  return new Date(s)
}
