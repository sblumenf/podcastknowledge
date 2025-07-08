import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const panelVariants = {
  menu: {
    open: { x: 0, opacity: 1 },
    closed: { x: -180, opacity: 0.95 }
  },
  statements: {
    open: { x: 0, opacity: 1 },
    closed: { x: 340, opacity: 0.95 }
  }
}

function AnimatedPanel({ isOpen, variant = 'statements', children, className }) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial="closed"
          animate="open"
          exit="closed"
          variants={panelVariants[variant]}
          transition={{
            type: "spring",
            stiffness: 300,
            damping: 30,
            mass: 0.8
          }}
          className={className}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default AnimatedPanel