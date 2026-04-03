import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import AuroraBackground from '../components/AuroraBackground'

const cities = ['Cannes', 'Paris', 'Tokyo', 'Berlin', 'NYC', 'Lisbon', 'Bangkok', 'Barcelona']
const vibes = ['culture-maxx', 'spy-game', 'touch-grass', 'social-arc', 'chaos-mode', 'discovery']
const objectives = ['meet people', 'explore', 'get fit', 'eat well', 'learn something', 'go hard']

function useRotatingText(items: string[], interval = 2200) {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setIndex((i) => (i + 1) % items.length), interval)
    return () => clearInterval(timer)
  }, [items.length, interval])
  return items[index]
}

function QuestBuilderMockup() {
  const city = useRotatingText(cities, 2000)
  const vibe = useRotatingText(vibes, 2600)
  const objective = useRotatingText(objectives, 3000)

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="relative w-full max-w-xl mx-auto mt-14"
    >
      {/* Multi-color glow behind card */}
      <div className="absolute -inset-6 rounded-3xl blur-3xl opacity-30"
        style={{ background: 'conic-gradient(from 180deg, #7c5cff, #ff6b4a, #00e5ff, #7c5cff)' }}
      />

      <div className="relative bg-surface/90 border border-indigo/15 rounded-2xl p-6 backdrop-blur-xl shadow-2xl shadow-indigo/5">
        {/* Terminal header */}
        <div className="flex items-center gap-2 mb-5 pb-3 border-b border-elevated/60">
          <div className="w-3 h-3 rounded-full bg-coral/70" />
          <div className="w-3 h-3 rounded-full bg-gold/70" />
          <div className="w-3 h-3 rounded-full bg-neon/70" />
          <span className="ml-3 font-mono text-xs text-dim">
            quest.config.ts
          </span>
        </div>

        {/* Config fields */}
        <div className="space-y-3 font-mono text-sm">
          {[
            { key: 'city', value: city, color: 'text-coral' },
            { key: 'vibe', value: vibe, color: 'text-indigo' },
            { key: 'objective', value: objective, color: 'text-cyan' },
            { key: 'time', value: '3h', color: 'text-bone', static: true },
            { key: 'budget', value: '$$', color: 'text-gold', static: true },
            { key: 'party', value: 'duo', color: 'text-phantom', static: true },
          ].map((field) => (
            <div key={field.key} className="flex items-center gap-3">
              <span className="text-dim w-24 text-right shrink-0">{field.key}:</span>
              <div className="flex-1 bg-base/50 border border-elevated/40 rounded-lg px-3 py-2">
                {field.static ? (
                  <span className={field.color}>"{field.value}"</span>
                ) : (
                  <motion.span
                    key={field.value}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={field.color}
                  >
                    "{field.value}"
                  </motion.span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Run indicator */}
        <div className="mt-5 pt-4 border-t border-elevated/40">
          <div className="flex items-center gap-2 font-mono text-xs text-neon/80">
            <span className="animate-blink">_</span>
            <span>ready to instantiate quest...</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export default function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center px-6 pt-20 pb-16 overflow-hidden">
      <AuroraBackground />

      <div className="relative z-10 max-w-4xl mx-auto text-center">
        {/* Tagline chip */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full border border-indigo/20 bg-indigo/5 text-xs font-mono text-muted backdrop-blur-sm"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-coral animate-pulse-glow" />
          AI dungeon master for your actual life
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-black tracking-tight leading-[0.95] mb-6"
        >
          <span className="block text-bone">Stop rawdogging</span>
          <span
            className="block bg-clip-text text-transparent"
            style={{
              backgroundImage: 'linear-gradient(135deg, #ff6b4a, #7c5cff, #00e5ff)',
              backgroundSize: '200% 200%',
              animation: 'gradient-x 6s ease infinite',
            }}
          >
            your weekends.
          </span>
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-lg sm:text-xl text-muted max-w-2xl mx-auto mb-10 leading-relaxed"
        >
          Your city is an open world. OpenD&D turns it into a quest&mdash;adapted
          to your goals, time, budget, and crew. Real places. Real adventures.
          Actually fun.
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.45 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <a
            href="#cta"
            className="group relative px-8 py-3.5 bg-coral text-white font-semibold text-sm rounded-xl hover:shadow-[0_0_30px_rgba(255,107,74,0.35)] transition-all duration-300"
          >
            <span className="relative z-10 flex items-center gap-2">
              Launch your quest
              <svg
                className="w-4 h-4 transition-transform group-hover:translate-x-1"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </span>
          </a>
          <a
            href="#pipeline"
            className="px-8 py-3.5 border border-elevated text-bone text-sm font-medium rounded-xl hover:bg-elevated/30 hover:border-indigo/20 transition-all duration-200"
          >
            See how it works
          </a>
        </motion.div>

        {/* Quest builder mockup */}
        <QuestBuilderMockup />
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5, duration: 0.8 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <div className="flex flex-col items-center gap-2 text-dim">
          <span className="text-xs font-mono">scroll to explore</span>
          <motion.div
            animate={{ y: [0, 6, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7" />
            </svg>
          </motion.div>
        </div>
      </motion.div>
    </section>
  )
}
