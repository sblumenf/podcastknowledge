import ReactMarkdown from 'react-markdown'
import type { ChatMessage } from '../types'
import styles from './Message.module.css'

interface MessageProps {
  message: ChatMessage
}

export function Message({ message }: MessageProps) {
  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  
  return (
    <div className={`${styles.message} ${styles[message.role]}`}>
      {message.role === 'assistant' && (
        <div className={styles.avatar}>AI</div>
      )}
      <div className={styles.messageWrapper}>
        <div className={styles.messageContent}>
          {message.role === 'assistant' ? (
            <div className={styles.markdown}>
              <ReactMarkdown
                components={{
                  // Custom components for markdown elements
                  p: ({ children }) => <p className={styles.paragraph}>{children}</p>,
                  code: ({ children, className }) => {
                    const isInline = !className
                    return isInline ? (
                      <code className={styles.inlineCode}>{children}</code>
                    ) : (
                      <pre className={styles.codeBlock}>
                        <code>{children}</code>
                      </pre>
                    )
                  },
                  ul: ({ children }) => <ul className={styles.list}>{children}</ul>,
                  ol: ({ children }) => <ol className={styles.list}>{children}</ol>,
                  li: ({ children }) => <li className={styles.listItem}>{children}</li>,
                  blockquote: ({ children }) => <blockquote className={styles.blockquote}>{children}</blockquote>,
                  h1: ({ children }) => <h3 className={styles.heading}>{children}</h3>,
                  h2: ({ children }) => <h3 className={styles.heading}>{children}</h3>,
                  h3: ({ children }) => <h4 className={styles.heading}>{children}</h4>,
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className={styles.plainText}>{message.content}</div>
          )}
        </div>
        {message.timestamp && (
          <div className={styles.timestamp}>
            {formatTimestamp(message.timestamp)}
          </div>
        )}
      </div>
    </div>
  )
}