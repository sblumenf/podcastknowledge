import './App.css'
import { Routes, Route } from 'react-router-dom'
import { Dashboard } from './components/Dashboard'
import { ThreePanelLayout } from './components/ThreePanelLayout'

function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/podcast/:id" element={<ThreePanelLayout />} />
      </Routes>
    </div>
  )
}

export default App