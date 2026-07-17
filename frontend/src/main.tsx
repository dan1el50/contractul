import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { Router } from '@/app/router'
import { AuthProvider } from '@/features/auth/AuthContext'
import '@/styles/global.css'

const container = document.getElementById('root')
if (!container) throw new Error('Root element #root not found in index.html')

createRoot(container).render(
  <StrictMode>
    <AuthProvider>
      <Router />
    </AuthProvider>
  </StrictMode>,
)
