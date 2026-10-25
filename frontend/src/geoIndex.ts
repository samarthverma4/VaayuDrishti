import { useQuery } from '@tanstack/react-query'
import type { DistrictMeta } from './api'

export const useDistrictIndex = () =>
  useQuery({
    queryKey: ['district-index'],
    queryFn: async () => (await fetch('/api/v1/assets/geo/districts_index.json')).json() as Promise<DistrictMeta[]>,
  })

/** Nearest district centroid to a point, with distance in km. */
export function nearestDistrict(idx: DistrictMeta[] | undefined, lat: number, lon: number) {
  if (!idx?.length) return null
  let best: DistrictMeta | null = null
  let bd = Infinity
  for (const d of idx) {
    const dy = (d.centroid[1] - lat) * 111.2
    const dx = (d.centroid[0] - lon) * 111.2 * Math.cos((lat * Math.PI) / 180)
    const dist = Math.hypot(dx, dy)
    if (dist < bd) { bd = dist; best = d }
  }
  return best ? { district: best, km: bd } : null
}
