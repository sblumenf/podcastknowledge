import React from 'react'
import { useParams } from 'react-router-dom'
import GraphVisualization from '../components/GraphVisualization'

function PodcastView() {
  const { podcastId } = useParams()

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0 }}>
      <GraphVisualization podcastId={podcastId} />
    </div>
  )
}

export default PodcastView