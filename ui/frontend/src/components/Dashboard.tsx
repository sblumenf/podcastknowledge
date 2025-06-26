import { useState, useEffect } from 'react';
import styles from './Dashboard.module.css';

interface Podcast {
  id: string;
  name: string;
  host: string;
  category: string;
  description: string;
  tags: string[];
  enabled: boolean;
  database_port: number | string;
  database_name: string;
}

interface DashboardProps {
  onSelectPodcast: (podcast: { id: string; name: string }) => void;
}

export function Dashboard({ onSelectPodcast }: DashboardProps) {
  const [podcasts, setPodcasts] = useState<Podcast[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('http://localhost:8001/api/podcasts')
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch podcasts');
        }
        return response.json();
      })
      .then(data => {
        setPodcasts(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading podcasts...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>Error: {error}</div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Podcast Knowledge</h1>
        <p className={styles.subtitle}>Discover insights from your favorite podcasts</p>
      </header>

      <main className={styles.main}>
        <div className={styles.grid}>
          {podcasts.map((podcast) => (
            <div 
              key={podcast.id} 
              className={styles.card}
              onClick={() => onSelectPodcast({ id: podcast.id, name: podcast.name })}
            >
              <div className={styles.cardContent}>
                <div className={styles.cardHeader}>
                  <h2 className={styles.podcastName}>{podcast.name}</h2>
                  <span className={styles.category}>{podcast.category}</span>
                </div>
                
                <div className={styles.cardBody}>
                  <p className={styles.host}>Hosted by {podcast.host}</p>
                  <p className={styles.description}>{podcast.description}</p>
                  
                  <div className={styles.metadata}>
                    <div className={styles.tags}>
                      {podcast.tags.map((tag, index) => (
                        <span key={index} className={styles.tag}>{tag}</span>
                      ))}
                    </div>
                    
                    <div className={styles.databaseInfo}>
                      <span className={styles.port}>Port: {podcast.database_port}</span>
                      <span className={styles.dbName}>DB: {podcast.database_name}</span>
                    </div>
                  </div>
                </div>

                <div className={styles.status}>
                  <span className={podcast.enabled ? styles.enabled : styles.disabled}>
                    {podcast.enabled ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}