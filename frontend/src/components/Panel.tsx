import { useStore } from '../store'
import { AtmospherePanel } from './panels/AtmospherePanel'
import { DataPanel } from './panels/DataPanel'
import { DistrictsPanel } from './panels/DistrictsPanel'
import { EventPanel } from './panels/EventPanel'
import { EvolutionPanel } from './panels/EvolutionPanel'
import { ModelsPanel } from './panels/ModelsPanel'
import { VerificationPanel } from './panels/VerificationPanel'

export function Panel() {
  const { section, eventId } = useStore()
  return (
    <div className="space-y-5 p-4 pb-20 lg:pb-6">
      {section === 'atmosphere' && (eventId ? <EventPanel /> : <AtmospherePanel />)}
      {section === 'events' && (eventId ? <EventPanel /> : <AtmospherePanel />)}
      {section === 'evolution' && <EvolutionPanel />}
      {section === 'districts' && <DistrictsPanel />}
      {section === 'models' && <ModelsPanel />}
      {section === 'verification' && <VerificationPanel />}
      {section === 'data' && <DataPanel />}
    </div>
  )
}
