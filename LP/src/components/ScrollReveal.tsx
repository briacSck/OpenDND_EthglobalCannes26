import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  delay?: number
  className?: string
  direction?: 'up' | 'left' | 'right'
}

export default function ScrollReveal({
  children,
  delay = 0,
  className = '',
  direction = 'up',
}: Props) {
  const offsets = {
    up: { y: 32, x: 0 },
    left: { y: 0, x: -32 },
    right: { y: 0, x: 32 },
  }

  return (
    <motion.div
      initial={{ opacity: 0, ...offsets[direction] }}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.6, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}
