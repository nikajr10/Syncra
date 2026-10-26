import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import '@/components/arc/foundation.css'
import '@/styles/index.css'
import { queryClient } from '@/lib/queryClient'
import App from './App'

// Arc's dark theme keys off data-theme: follow the system setting.
const dark = matchMedia('(prefers-color-scheme: dark)')
const applyTheme = () => { document.documentElement.dataset.theme = dark.matches ? 'dark' : 'light' }
applyTheme()
dark.addEventListener('change', applyTheme)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
