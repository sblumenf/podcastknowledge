import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { LayoutProvider } from './contexts/LayoutContext'
import Dashboard from './pages/Dashboard'
import PodcastView from './pages/PodcastView'

function App() {
  return (
    <ThemeProvider>
      <LayoutProvider>
        <Router>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/podcast/:podcastId" element={<PodcastView />} />
          </Routes>
        </Router>
      </LayoutProvider>
    </ThemeProvider>
  )
}

export default App