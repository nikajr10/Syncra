import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@/components/arc/foundation.css'
import './index.css'
import App from './App'

// Arc's dark theme keys off data-theme: follow the system setting.
const dark = matchMedia('(prefers-color-scheme: dark)')
const applyTheme = () => { document.documentElement.dataset.theme = dark.matches ? 'dark' : 'light' }
applyTheme()
dark.addEventListener('change', applyTheme)

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
