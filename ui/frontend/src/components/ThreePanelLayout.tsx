import { useParams } from 'react-router-dom'

export function ThreePanelLayout() {
  const { id } = useParams<{ id: string }>()
  
  return (
    <div>
      <h1>Three Panel Layout</h1>
      <p>Podcast ID: {id}</p>
      <p>Three-panel layout placeholder - Phase 3 implementation pending</p>
    </div>
  )
}