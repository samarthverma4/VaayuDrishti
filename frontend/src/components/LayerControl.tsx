import { Layers } from 'lucide-react'
import { useState } from 'react'
import type { LayerKey } from '../api'
import { fmtUtc, LAYER_LABEL } from '../format'
import { useSelection } from '../hooks'
import { windowForLead } from '../map/data'
import { useStore } from '../store'

export function LayerControl() {
  const { fields } = useSelection()
  const { layer, showIsobars, leadH, set } = useStore()
  const [open, setOpen] = useState(false)
  if (!fields.data) return null
  const keys = Object.keys(fields.data.layers) as LayerKey[]
  const legend = layer === 'rain_mean' ? fields.data.legends.rain : fields.data.legends.prob
  const w = fields.data.windows[windowForLead(fields.data, leadH)]
  const grad = `linear-gradient(90deg, ${legend.stops.map((s, i) => `rgba(${s.rgba[0]},${s.rgba[1]},${s.rgba[2]},${Math.max(s.rgba[3] / 255, 0.15)}) ${(i / (legend.stops.length - 1)) * 100}%`).join(',')})`

  return (
    <div className="absolute right-14 top-3 z-10 w-[236px] rounded border hairline bg-abyss/90 text-xs backdrop-blur-sm">
      <button className="flex w-full items-center justify-between px-2.5 py-1.5" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="flex items-center gap-1.5 font-display font-medium"><Layers size={13} /> Layers</span>
        <span className="label">{layer === 'none' ? 'off' : LAYER_LABEL[layer]}</span>
      </button>
      {!open && layer !== 'none' && (
        <div className="border-t hairline px-2.5 py-1.5">
          <div className="h-1.5 rounded-sm" style={{ background: grad }} />
          {w && <p className="mt-1 num text-[9px] text-muted">{fmtUtc(w.valid_start)} → {fmtUtc(w.valid_end)}</p>}
        </div>
      )}
      {open && (
        <div className="space-y-2 border-t hairline px-2.5 py-2">
          <fieldset className="space-y-1">
            <legend className="sr-only">Gridded layer</legend>
            {[...keys, 'none' as const].map((k) => (
              <label key={k} className="flex cursor-pointer items-center gap-2">
                <input type="radio" name="layer" checked={layer === k} onChange={() => set({ layer: k })} className="accent-[#66DCE7]" />
                <span className={layer === k ? 'text-ink' : 'text-muted'}>{k === 'none' ? 'No gridded layer' : LAYER_LABEL[k]}</span>
              </label>
            ))}
          </fieldset>
          <label className="flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={showIsobars} onChange={(e) => set({ showIsobars: e.target.checked })} className="accent-[#66DCE7]" />
            <span className="text-muted">Ensemble-mean isobars (2 hPa)</span>
          </label>
          {layer !== 'none' && (
            <div>
              <div className="h-2 rounded-sm" style={{ background: grad }} />
              <div className="mt-0.5 flex justify-between num text-[9px] text-muted">
                {legend.stops.filter((_, i) => i % 2 === 0 || i === legend.stops.length - 1).map((s) => (
                  <span key={s.value}>{legend.kind === 'prob' ? `${Math.round(s.value * 100)}%` : s.value}</span>
                ))}
              </div>
              <p className="mt-1 text-[10px] leading-snug text-muted">{fields.data.definitions[layer]}</p>
              {w && <p className="mt-1 num text-[10px] text-muted">Window {fmtUtc(w.valid_start)} → {fmtUtc(w.valid_end)}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
