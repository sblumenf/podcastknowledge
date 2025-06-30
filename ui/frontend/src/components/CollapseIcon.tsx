interface CollapseIconProps {
  direction: 'left' | 'right'
  className?: string
}

export function CollapseIcon({ direction, className = '' }: CollapseIconProps) {
  return (
    <svg 
      width="16" 
      height="16" 
      viewBox="0 0 16 16" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {direction === 'left' ? (
        <path 
          d="M5 2 L5 14 M10 2 L10 14" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round"
        />
      ) : (
        <path 
          d="M6 2 L6 14 M11 2 L11 14" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round"
        />
      )}
    </svg>
  )
}