import './App.css'
import { Routes, Route } from 'react-router-dom'
import { Dashboard } from './components/Dashboard'
import { ThreePanelLayout } from './components/ThreePanelLayout'
import { ErrorBoundary } from './components/ErrorBoundary'

function App() {
  return (
    <ErrorBoundary>
      <div className="app">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/podcast/:id" element={<ThreePanelLayout />} />
        </Routes>
      </div>
    </ErrorBoundary>
  )
}

export default App