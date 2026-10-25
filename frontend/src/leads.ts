/** ECMWF ENS output steps: 3-hourly to T+144, then 6-hourly. */
export function outputLeads(maxLead: number) {
  const out: number[] = []
  for (let h = 0; h <= Math.min(144, maxLead); h += 3) out.push(h)
  for (let h = 150; h <= maxLead; h += 6) out.push(h)
  return out
}
