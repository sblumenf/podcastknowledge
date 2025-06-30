export function ChatBubbleIcon({ className = '' }: { className?: string }) {
  return (
    <svg 
      width="24" 
      height="24" 
      viewBox="0 0 24 24" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path 
        d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" 
        fill="currentColor"
      />
    </svg>
  )
}

export function EpisodeIcon({ number, className = '' }: { number: number, className?: string }) {
  return (
    <div className={`episodeIcon ${className}`}>
      <svg 
        width="24" 
        height="24" 
        viewBox="0 0 24 24" 
        fill="none" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect 
          x="3" 
          y="3" 
          width="18" 
          height="18" 
          rx="4" 
          stroke="currentColor" 
          strokeWidth="1.5"
        />
        <text 
          x="50%" 
          y="50%" 
          dominantBaseline="middle" 
          textAnchor="middle" 
          fill="currentColor"
          fontSize="12"
          fontWeight="500"
        >
          {number}
        </text>
      </svg>
    </div>
  )
}

export function AddIcon({ className = '' }: { className?: string }) {
  return (
    <svg 
      width="24" 
      height="24" 
      viewBox="0 0 24 24" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path 
        d="M12 5v14m-7-7h14" 
        stroke="currentColor" 
        strokeWidth="2" 
        strokeLinecap="round"
      />
    </svg>
  )
}