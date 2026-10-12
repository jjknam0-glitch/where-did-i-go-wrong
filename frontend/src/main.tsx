import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ToastProvider } from './components/ui'
import { FlowProvider } from './lib/flow'
import { StoreProvider } from './lib/store'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <StoreProvider>
        <FlowProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </FlowProvider>
      </StoreProvider>
    </BrowserRouter>
  </StrictMode>,
)
