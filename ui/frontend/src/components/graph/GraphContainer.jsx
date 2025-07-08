import React, { useEffect, useRef, useState } from 'react'
import { SigmaContainer, useRegisterEvents, useLoadGraph, useSigma } from '@react-sigma/core'
import '@react-sigma/core/lib/react-sigma.min.css'
import Graph from 'graphology'

function GraphEvents({ onNodeSelect }) {
  const registerEvents = useRegisterEvents()
  const sigma = useSigma()
  
  useEffect(() => {
    registerEvents({
      clickNode: (event) => {
        const nodeId = event.node
        const nodeData = sigma.getGraph().getNodeAttributes(nodeId)
        onNodeSelect({ id: nodeId, ...nodeData })
        
        // Handle node expansion
        if (nodeData.type === 'cluster' || nodeData.type === 'topic') {
          expandNode(nodeId)
        }
      },
      enterNode: () => {
        document.body.style.cursor = 'pointer'
      },
      leaveNode: () => {
        document.body.style.cursor = 'default'
      }
    })
  }, [registerEvents, sigma, onNodeSelect])
  
  const expandNode = async (nodeId) => {
    // This will be implemented to fetch and add child nodes
    console.log('Expanding node:', nodeId)
  }
  
  return null
}

function GraphLoader({ podcastId, podcast }) {
  const loadGraph = useLoadGraph()
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    const loadInitialGraph = async () => {
      try {
        const response = await fetch(
          `/api/v1/graph/${podcastId}/initial?uri=${encodeURIComponent(podcast.database.uri)}`
        )
        const data = await response.json()
        
        const graph = new Graph()
        
        // Add nodes
        data.nodes.forEach(node => {
          graph.addNode(node.id, {
            label: node.label,
            size: node.size,
            color: node.color,
            type: node.type,
            x: Math.random() * 100,
            y: Math.random() * 100,
            hidden: node.hidden || false
          })
        })
        
        // Add edges
        data.edges.forEach(edge => {
          if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
            graph.addEdge(edge.source, edge.target, {
              size: edge.size || 1,
              color: '#e0e0e0'
            })
          }
        })
        
        loadGraph(graph)
        setLoading(false)
      } catch (error) {
        console.error('Failed to load graph:', error)
        setLoading(false)
      }
    }
    
    if (podcast) {
      loadInitialGraph()
    }
  }, [podcastId, podcast, loadGraph])
  
  return loading ? (
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent" />
    </div>
  ) : null
}

function GraphContainer({ podcastId, podcast, onNodeSelect }) {
  if (!podcast) return null
  
  return (
    <SigmaContainer
      style={{ height: '100%', width: '100%' }}
      settings={{
        renderLabels: true,
        labelRenderedSizeThreshold: 5,
        defaultNodeColor: '#666',
        defaultEdgeColor: '#e0e0e0',
        labelFont: 'Arial',
        labelSize: 12,
        labelWeight: 'normal',
        labelColor: { color: '#000' }
      }}
    >
      <GraphLoader podcastId={podcastId} podcast={podcast} />
      <GraphEvents onNodeSelect={onNodeSelect} />
    </SigmaContainer>
  )
}

export default GraphContainer