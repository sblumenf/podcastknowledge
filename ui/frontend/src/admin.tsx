import React from 'react'
import ReactDOM from 'react-dom/client'
import Admin from './Admin.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('admin-root')!).render(
  <React.StrictMode>
    <Admin />
  </React.StrictMode>,
)