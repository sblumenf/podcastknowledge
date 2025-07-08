import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useLayout } from '../contexts/LayoutContext'
import MenuPanel from '../components/panels/MenuPanel'
import GraphContainer from '../components/graph/GraphContainer'
import StatementsPanel from '../components/panels/StatementsPanel'
import SettingsPanel from '../components/panels/SettingsPanel'
import GraphControls from '../components/graph/GraphControls'
import FixedHamburger from '../components/FixedHamburger'

function PodcastView() {
  const { podcastId } = useParams()
  const navigate = useNavigate()
  const [podcast, setPodcast] = useState(null)
  const [loading, setLoading] = useState(true)
  const { menu, statements, settings } = useLayout()
  const [selectedNode, setSelectedNode] = useState(null)
  
  useEffect(() => {
    fetchPodcastDetails()
  }, [podcastId])
  
  const fetchPodcastDetails = async () => {
    try {
      const response = await fetch(`/api/v1/podcasts/${podcastId}`)
      const data = await response.json()
      setPodcast(data)
      
      // Connect to the specific Neo4j instance for this podcast
      await connectToGraphDatabase(data.database.port)
    } catch (error) {
      console.error('Failed to fetch podcast details:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const connectToGraphDatabase = async (port) => {
    // This establishes the connection context for the graph
    console.log(`Connecting to Neo4j on port ${port}`)
  }
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a1a1a] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent" />
      </div>
    )
  }
  
  return (
    <div className="h-screen w-screen overflow-hidden relative bg-background">
      {/* Background graph layer */}
      <div 
        id="graph-container" 
        className="absolute inset-0 z-0"
        style={{ 
          left: '-50px',
          paddingLeft: '40px',
          paddingRight: '40px',
          zIndex: -1
        }}>
        <GraphContainer 
          podcastId={podcastId} 
          podcast={podcast}
          onNodeSelect={setSelectedNode}
        />
      </div>
      
      {/* Three-panel overlay structure */}
      <div className="relative h-full z-10 grid grid-cols-[auto_1fr_auto] transition-all duration-300 ease-out">
        {/* Left Menu Panel - 180px */}
        <aside
          ref={menu.panelRef}
          className={`w-[180px] h-full bg-white/95 dark:bg-gray-900/95 glass-panel border-r border-gray-200 dark:border-gray-700 z-20 panel-shadow transition-all duration-300 ease-out ${
            menu.isOpen ? '' : '-ml-[180px]'
          }`}
        >
          <MenuPanel podcast={podcast} onBack={() => navigate('/')} />
        </aside>
        
        {/* Center Graph Area */}
        <main className="relative flex-1">
          {/* Graph controls overlay on top of background graph */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="pointer-events-auto">
              <GraphControls />
            </div>
          </div>
          
          {/* Fixed hamburger menu */}
          <FixedHamburger />
        </main>
        
        {/* Right Statements Panel - 340px */}
        <aside
          ref={statements.panelRef}
          className={`w-[340px] h-full bg-white/90 dark:bg-gray-900/90 glass-panel border-l border-gray-200 dark:border-gray-700 z-20 panel-shadow overflow-hidden transition-all duration-300 ease-out ${
            statements.isOpen ? '' : '-mr-[340px]'
          }`}
        >
          <StatementsPanel selectedNode={selectedNode} />
        </aside>
        
      </div>
      
      {/* Settings Panel - 250px - Outside grid */}
      <aside
        ref={settings.panelRef}
        className={`fixed right-0 top-0 w-[250px] h-full bg-white/90 dark:bg-gray-900/90 glass-panel border-l border-gray-200 dark:border-gray-700 z-30 panel-shadow overflow-hidden transition-all duration-300 ease-out ${
          settings.isOpen ? '' : 'translate-x-full'
        }`}
      >
        <SettingsPanel onClose={settings.toggle} />
      </aside>
    </div>
  )
}

export default PodcastView