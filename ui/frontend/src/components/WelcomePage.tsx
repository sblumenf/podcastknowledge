import './WelcomePage.module.css'

function WelcomePage() {
  return (
    <div className="welcome-page">
      <header className="welcome-header">
        <h1>Podcast Knowledge Explorer</h1>
        <p className="description">
          Explore knowledge graphs from your favorite podcasts
        </p>
      </header>
      
      <section className="coming-soon">
        <h2>Coming Soon</h2>
        <ul className="feature-list">
          <li>Interactive knowledge graph visualization</li>
          <li>Search across all podcast content</li>
          <li>Topic exploration and discovery</li>
          <li>AI-powered insights and summaries</li>
        </ul>
      </section>
    </div>
  )
}

export default WelcomePage