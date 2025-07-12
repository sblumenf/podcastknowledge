import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import ForceGraph3D from 'react-force-graph-3d'

// Style constants
const BACK_BUTTON_STYLE = {
  position: 'absolute',
  top: '20px',
  left: '20px',
  background: 'rgba(0, 0, 0, 0.5)',
  border: '1px solid rgba(255, 255, 255, 0.2)',
  color: '#fff',
  padding: '8px 16px',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '14px',
  zIndex: 1000,
  transition: 'background 0.3s'
}

const SELECTED_NODE_PANEL_STYLE = {
  position: 'absolute',
  top: '20px',
  right: '20px',
  background: 'rgba(0, 0, 0, 0.8)',
  padding: '10px',
  borderRadius: '5px',
  color: '#fff',
  maxWidth: '300px',
  zIndex: 1000
}

function GraphVisualization({ podcastId }) {
  const navigate = useNavigate()
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState(null)
  const fgRef = useRef()

  useEffect(() => {
    fetchGraphData()
  }, [podcastId])

  const fetchGraphData = async () => {
    try {
      const response = await fetch(`/api/v1/podcasts/${podcastId}/meaningful-units`)
      if (!response.ok) throw new Error('Failed to fetch graph data')
      const data = await response.json()
      setGraphData(data)
    } catch (err) {
      console.error('Error fetching graph data:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleNodeClick = (node) => {
    setSelectedNode(node)
  }

  if (loading) return <div style={{ color: '#a0a0a0' }}>Loading graph...</div>

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        nodeLabel="name"
        nodeAutoColorBy="cluster"
        onNodeClick={handleNodeClick}
        linkOpacity={0.2}
        nodeOpacity={0.9}
        backgroundColor="#000011"
        width={window.innerWidth}
        height={window.innerHeight}
      />
      <button
        onClick={() => navigate('/')}
        style={BACK_BUTTON_STYLE}
        onMouseEnter={(e) => e.target.style.background = 'rgba(0, 0, 0, 0.8)'}
        onMouseLeave={(e) => e.target.style.background = 'rgba(0, 0, 0, 0.5)'}
      >
        ← Back to Dashboard
      </button>
      {selectedNode && (
        <div style={SELECTED_NODE_PANEL_STYLE}>
          <h4 style={{ margin: '0 0 10px 0' }}>Selected Unit</h4>
          <p style={{ margin: 0 }}>{selectedNode.name}</p>
          {selectedNode.themes && (
            <p style={{ margin: '5px 0 0 0', fontSize: '0.9em', color: '#a0a0a0' }}>
              Themes: {selectedNode.themes}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default GraphVisualization