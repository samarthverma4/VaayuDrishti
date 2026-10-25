import { Database, GitCompareArrows, Globe2, MapPinned, Radar, ServerCog, Target } from 'lucide-react'
import { type Section, useStore } from '../store'

const ITEMS: { id: Section; label: string; Icon: typeof Globe2 }[] = [
  { id: 'atmosphere', label: 'Atmosphere', Icon: Globe2 },
  { id: 'events', label: 'Events', Icon: Radar },
  { id: 'evolution', label: 'Evolution', Icon: GitCompareArrows },
  { id: 'districts', label: 'Districts', Icon: MapPinned },
  { id: 'models', label: 'Models', Icon: ServerCog },
  { id: 'verification', label: 'Verification', Icon: Target },
  { id: 'data', label: 'Data & Export', Icon: Database },
]

export function NavRail() {
  const { section, set } = useStore()
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex h-14 border-t hairline bg-abyss md:static md:h-auto md:w-[68px] md:shrink-0 md:flex-col md:border-r md:border-t-0 md:py-2"
      aria-label="Sections"
    >
      {ITEMS.map(({ id, label, Icon }) => (
        <button
          key={id}
          onClick={() => set({ section: id, panelOpen: true })}
          aria-current={section === id ? 'page' : undefined}
          className={`group relative flex flex-1 flex-col items-center justify-center gap-1 py-2 text-[9px] md:flex-none md:py-3 ${section === id ? 'text-ion' : 'text-muted hover:text-ink'}`}
        >
          {section === id && <span className="absolute left-0 top-2 bottom-2 hidden w-[2px] bg-ion md:block" />}
          <Icon size={18} strokeWidth={1.6} />
          <span className="leading-none">{label}</span>
        </button>
      ))}
    </nav>
  )
}
