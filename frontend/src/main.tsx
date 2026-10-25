import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { setWorkerUrl } from 'maplibre-gl'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// Served untransformed from public/ (copied from node_modules by `npm run copy-worker`).
setWorkerUrl('/maplibre-gl-worker.mjs')

const client = new QueryClient({
  defaultOptions: { queries: { staleTime: Infinity, retry: (n, err) => n < 1 && (err as { status?: number }).status !== 404 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
