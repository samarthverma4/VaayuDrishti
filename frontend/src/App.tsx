import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import { EventList } from './components/EventList'
import { LayerControl } from './components/LayerControl'
import { NavRail } from './components/NavRail'
import { Panel } from './components/Panel'
import { TimeRibbon } from './components/TimeRibbon'
import { TopBar } from './components/TopBar'
import { MapCanvas } from './map/MapCanvas'
import { StabilityLens } from './map/StabilityLens'
import { useStore } from './store'

export default function App() {
  const { section, panelOpen, set } = useStore()
  const showList = section === 'atmosphere' || section === 'events'
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <NavRail />
        {showList && (
          <aside className="hidden w-[264px] shrink-0 flex-col border-r hairline bg-ocean md:flex" aria-label="Events">
            <EventList />
          </aside>
        )}
        <main className="relative flex min-w-0 flex-1 flex-col">
          <div className="relative min-h-0 flex-1">
            <MapCanvas />
            {section === 'evolution' && <StabilityLens />}
            <LayerControl />
            <button
              onClick={() => set({ panelOpen: !panelOpen })}
              className="absolute right-3 top-3 z-20 hidden h-8 w-8 place-items-center rounded border hairline bg-abyss/85 text-muted hover:text-ink lg:grid"
              aria-label={panelOpen ? 'Collapse the intelligence panel' : 'Open the intelligence panel'}
            >
              {panelOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
            </button>
          </div>
          <div className="h-[64px] shrink-0 border-t hairline bg-ocean">
            <TimeRibbon />
          </div>
        </main>
        {panelOpen && (
          <aside
            className="fixed inset-x-0 bottom-[64px] z-30 max-h-[55vh] overflow-y-auto border-t hairline bg-ocean scroll-thin lg:static lg:max-h-none lg:w-[400px] lg:shrink-0 lg:border-l lg:border-t-0"
            aria-label="Intelligence panel"
          >
            <Panel />
          </aside>
        )}
      </div>
    </div>
  )
}
