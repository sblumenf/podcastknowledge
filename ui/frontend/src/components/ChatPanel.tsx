import { useState, useRef, useEffect } from 'react'
import type { ChatMessage } from '../types'
import { Message } from './Message'
import styles from './ChatPanel.module.css'

interface ChatPanelProps {
  podcastId: string
}

const MAX_MESSAGES = 50 // Limit message history for performance

export function ChatPanel({ podcastId }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  
  useEffect(() => {
    scrollToBottom()
  }, [messages])
  
  // Clear chat when switching podcasts
  useEffect(() => {
    setMessages([])
    setInputValue('')
    setIsLoading(false)
  }, [podcastId])
  
  // Reset textarea height when input is cleared
  useEffect(() => {
    if (textareaRef.current && !inputValue) {
      textareaRef.current.style.height = 'auto'
    }
  }, [inputValue])
  
  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return
    
    const userMessage: ChatMessage = {
      role: 'user',
      content: inputValue,
      timestamp: new Date().toISOString()
    }
    
    setMessages(prev => [...prev, userMessage].slice(-MAX_MESSAGES))
    setInputValue('')
    setIsLoading(true)
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8002'}/api/chat/${podcastId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: inputValue })
      })
      
      if (!response.ok) {
        if (response.status === 503) {
          throw new Error('The chat service is temporarily unavailable. Please try again in a moment.')
        } else if (response.status === 404) {
          throw new Error('This podcast is not available for chat. Please try another podcast.')
        } else {
          throw new Error(`Unable to send message (${response.status})`)
        }
      }
      
      const data = await response.json()
      
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.response || 'Sorry, I could not process your request.',
        timestamp: new Date().toISOString()
      }
      
      setMessages(prev => [...prev, assistantMessage].slice(-MAX_MESSAGES))
    } catch (error) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: error instanceof Error ? error.message : 'Sorry, there was an error processing your request. Please try again.',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage].slice(-MAX_MESSAGES))
    } finally {
      setIsLoading(false)
    }
  }
  
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }
  
  return (
    <div className={styles.chatPanel}>
      <div className={styles.messagesContainer}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <p>Ask a question about this podcast!</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <Message key={index} message={message} />
          ))
        )}
        {isLoading && (
          <div className={`${styles.message} ${styles.assistant}`}>
            <div className={styles.messageContent}>
              <div className={styles.loading}>Thinking...</div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className={styles.inputContainer}>
        <textarea
          ref={textareaRef}
          className={styles.input}
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value)
            // Auto-resize to content
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
          }}
          onKeyPress={handleKeyPress}
          placeholder="Type your question..."
          disabled={isLoading}
          rows={1}
        />
        <button 
          className={styles.sendButton}
          onClick={handleSend}
          disabled={!inputValue.trim() || isLoading}
        >
          Send
        </button>
      </div>
    </div>
  )
}