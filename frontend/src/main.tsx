import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { SystemStatus } from '@/features/health/SystemStatus'
import '@/styles/global.css'

const container = document.getElementById('root')
if (!container) throw new Error('Root element #root not found in index.html')

createRoot(container).render(
  <StrictMode>
    <SystemStatus />
  </StrictMode>,
)
