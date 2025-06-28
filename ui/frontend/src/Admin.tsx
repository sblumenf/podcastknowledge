import React, { useState, useEffect } from 'react';

interface Podcast {
  id: string;
  name: string;
  enabled: string;
}

interface Episode {
  title: string;
  episode_date: string;
  youtube_url: string;
}

const Admin: React.FC = () => {
  const [podcasts, setPodcasts] = useState<Podcast[]>([]);
  const [selectedPodcast, setSelectedPodcast] = useState<string>('');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [showMissingOnly, setShowMissingOnly] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string>('');
  const [editingUrl, setEditingUrl] = useState<string>('');

  // Fetch podcasts on component mount
  useEffect(() => {
    fetchPodcasts();
  }, []);

  const fetchPodcasts = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/admin/podcasts');
      if (!response.ok) throw new Error('Failed to fetch podcasts');
      const data = await response.json();
      setPodcasts(data);
    } catch (err) {
      setError('Failed to load podcasts');
      console.error(err);
    }
  };

  const handlePodcastSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedPodcast(e.target.value);
    setEpisodes([]); // Clear previous results
  };

  const handleYouTubeUrlDiagnostic = async () => {
    if (!selectedPodcast) return;

    setLoading(true);
    setError('');
    
    try {
      const response = await fetch(`http://localhost:8000/api/admin/podcasts/${selectedPodcast}/youtube-urls`);
      if (!response.ok) throw new Error('Failed to fetch YouTube URLs');
      const data = await response.json();
      setEpisodes(data);
    } catch (err) {
      setError('Failed to load YouTube URLs');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (title: string, currentUrl: string) => {
    setEditingTitle(title);
    setEditingUrl(currentUrl || '');
  };

  const handleCancel = () => {
    setEditingTitle('');
    setEditingUrl('');
  };

  const handleSave = async (title: string) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/admin/podcasts/${selectedPodcast}/episodes/${encodeURIComponent(title)}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ youtube_url: editingUrl }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update YouTube URL');
      }

      // Update the local state
      setEpisodes(episodes.map(episode => 
        episode.title === title 
          ? { ...episode, youtube_url: editingUrl }
          : episode
      ));

      // Clear edit state
      setEditingTitle('');
      setEditingUrl('');
    } catch (err) {
      setError('Failed to update YouTube URL');
      console.error(err);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '15% 85%', height: '100vh', backgroundColor: '#242424', color: 'rgba(255, 255, 255, 0.87)' }}>
      {/* Left Pane */}
      <div style={{ padding: '20px', borderRight: '1px solid #444', backgroundColor: '#1a1a1a' }}>
        <h2>Admin Panel</h2>
        
        <div style={{ marginBottom: '20px' }}>
          <label htmlFor="podcast-select" style={{ display: 'block', marginBottom: '8px' }}>
            Select Podcast:
          </label>
          <select 
            id="podcast-select"
            value={selectedPodcast} 
            onChange={handlePodcastSelect}
            style={{ width: '100%', padding: '8px', backgroundColor: '#333', color: 'rgba(255, 255, 255, 0.87)', border: '1px solid #555' }}
          >
            <option value="">-- Select a podcast --</option>
            {podcasts.map((podcast) => (
              <option key={podcast.id} value={podcast.id}>
                {podcast.name}
              </option>
            ))}
          </select>
        </div>

        {selectedPodcast && (
          <div>
            <h3>Diagnostics</h3>
            <button 
              onClick={handleYouTubeUrlDiagnostic}
              style={{ 
                width: '100%', 
                padding: '10px', 
                marginBottom: '10px',
                cursor: 'pointer',
                backgroundColor: '#1a1a1a',
                color: 'rgba(255, 255, 255, 0.87)',
                border: '1px solid #444',
                borderRadius: '8px'
              }}
              disabled={loading}
            >
              YouTube URLs
            </button>
          </div>
        )}
      </div>

      {/* Right Pane */}
      <div style={{ padding: '20px', overflow: 'auto' }}>
        {error && (
          <div style={{ color: '#ff6b6b', marginBottom: '20px' }}>
            Error: {error}
          </div>
        )}

        {loading && <div>Loading...</div>}

        {episodes.length > 0 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2>Episodes - YouTube URLs</h2>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input 
                  type="checkbox" 
                  checked={showMissingOnly}
                  onChange={(e) => setShowMissingOnly(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                Show only episodes without YouTube URL
              </label>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ backgroundColor: '#333' }}>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>Title</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>Episode Date</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>YouTube URL</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {episodes
                  .filter(episode => !showMissingOnly || !episode.youtube_url)
                  .map((episode, index) => (
                    <tr key={index} style={{ backgroundColor: index % 2 === 0 ? '#1a1a1a' : '#242424' }}>
                      <td style={{ padding: '10px', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>{episode.title}</td>
                      <td style={{ padding: '10px', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>{episode.episode_date}</td>
                      <td style={{ padding: '10px', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>
                        {editingTitle === episode.title ? (
                          <input
                            type="text"
                            value={editingUrl}
                            onChange={(e) => setEditingUrl(e.target.value)}
                            style={{
                              backgroundColor: '#333',
                              color: 'rgba(255, 255, 255, 0.87)',
                              border: '1px solid #555',
                              padding: '4px',
                              width: '100%'
                            }}
                          />
                        ) : (
                          episode.youtube_url || '(missing)'
                        )}
                      </td>
                      <td style={{ padding: '10px', border: '1px solid #444', color: 'rgba(255, 255, 255, 0.87)' }}>
                        {editingTitle === episode.title ? (
                          <>
                            <button
                              onClick={() => handleSave(episode.title)}
                              style={{
                                backgroundColor: '#4CAF50',
                                color: 'white',
                                border: 'none',
                                padding: '5px 10px',
                                marginRight: '5px',
                                cursor: 'pointer',
                                borderRadius: '4px'
                              }}
                            >
                              Save
                            </button>
                            <button
                              onClick={handleCancel}
                              style={{
                                backgroundColor: '#f44336',
                                color: 'white',
                                border: 'none',
                                padding: '5px 10px',
                                cursor: 'pointer',
                                borderRadius: '4px'
                              }}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => handleEdit(episode.title, episode.youtube_url)}
                            style={{
                              backgroundColor: '#2196F3',
                              color: 'white',
                              border: 'none',
                              padding: '5px 10px',
                              cursor: 'pointer',
                              borderRadius: '4px'
                            }}
                          >
                            Edit
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && episodes.length === 0 && selectedPodcast && (
          <div style={{ textAlign: 'center', marginTop: '50px', color: '#666' }}>
            Select a diagnostic to view results
          </div>
        )}
      </div>
    </div>
  );
};

export default Admin;