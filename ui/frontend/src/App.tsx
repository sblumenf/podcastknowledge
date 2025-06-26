import './App.css'
import { useState } from 'react'
import { Dashboard } from './components/Dashboard'
import { Chat } from './components/Chat'

interface SelectedPodcast {
  id: string
  name: string
}

function App() {
  const [selectedPodcast, setSelectedPodcast] = useState<SelectedPodcast | null>(null)

  if (selectedPodcast) {
    return (
      <div className="app">
        <Chat 
          podcast={selectedPodcast} 
          onBack={() => setSelectedPodcast(null)} 
        />
      </div>
    )
  }

  return (
    <div className="app">
      <Dashboard onSelectPodcast={setSelectedPodcast} />
    </div>
  )
}

export default App