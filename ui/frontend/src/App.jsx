import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import PodcastView from './pages/PodcastView'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/podcast/:podcastId" element={<PodcastView />} />
      </Routes>
    </Router>
  )
}

export default App