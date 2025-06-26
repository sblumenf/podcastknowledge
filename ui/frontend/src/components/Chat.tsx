import { useState } from 'react';
import styles from './Chat.module.css';

interface ChatProps {
  podcast: {
    id: string;
    name: string;
  };
  onBack: () => void;
}

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
}

export function Chat({ podcast, onBack }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: input
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`http://localhost:8001/api/chat/${podcast.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: userMessage.content })
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();
      
      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.response
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <button className={styles.backButton} onClick={onBack}>
          ← Back
        </button>
        <h1 className={styles.title}>{podcast.name}</h1>
      </header>

      <div className={styles.chatArea}>
        <div className={styles.messages}>
          {messages.length === 0 && (
            <div className={styles.welcome}>
              <p>Welcome! Ask me anything about {podcast.name}.</p>
            </div>
          )}
          
          {messages.map((message) => (
            <div 
              key={message.id} 
              className={`${styles.message} ${styles[message.role]}`}
            >
              <div className={styles.messageContent}>
                {message.content}
              </div>
            </div>
          ))}
          
          {loading && (
            <div className={`${styles.message} ${styles.assistant}`}>
              <div className={styles.messageContent}>
                <span className={styles.typing}>Thinking...</span>
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className={styles.inputForm}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            className={styles.input}
            disabled={loading}
          />
          <button 
            type="submit" 
            className={styles.sendButton}
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}