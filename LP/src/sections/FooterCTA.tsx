import { motion } from 'framer-motion'
import ScrollReveal from '../components/ScrollReveal'

export default function FooterCTA() {
  return (
    <section id="cta" className="relative py-32 px-6 overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-neon/5 rounded-full blur-[120px]" />
      </div>

      <div className="relative max-w-3xl mx-auto text-center">
        <ScrollReveal>
          <span className="inline-block font-mono text-xs text-neon/60 tracking-widest uppercase mb-6">
            // ready_check
          </span>

          <h2 className="text-4xl sm:text-5xl md:text-6xl font-black tracking-tight text-bone mb-6 leading-[1.05]">
            Your city has a thousand<br />
            <span className="bg-gradient-to-r from-neon via-ice to-neon bg-clip-text text-transparent">
              side quests waiting.
            </span>
          </h2>

          <p className="text-lg text-muted max-w-xl mx-auto mb-10 leading-relaxed">
            Stop scrolling. Stop planning in your Notes app at 11pm.
            <br />
            Let the dungeon master cook.
          </p>

          <motion.div
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            className="inline-block"
          >
            <a
              href="#"
              className="inline-flex items-center gap-3 px-10 py-4 bg-neon text-void font-bold text-base rounded-xl hover:shadow-[0_0_40px_rgba(0,255,136,0.35)] transition-all duration-300"
            >
              Launch your first quest
              <svg
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </a>
          </motion.div>

          <p className="mt-6 text-xs font-mono text-dim">
            free to start · no credit card · quests in 30 seconds
          </p>
        </ScrollReveal>
      </div>

      {/* Footer bar */}
      <div className="relative mt-24 pt-8 border-t border-slate-light/15 max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-dim font-mono">
          <div className="flex items-center gap-2">
            <span className="text-neon font-bold">Open</span>
            <span className="text-bone font-bold">D&D</span>
            <span className="text-dim/50">·</span>
            <span>quest orchestrator</span>
          </div>
          <div className="flex items-center gap-4">
            <span>ETHGlobal Cannes 2026</span>
            <span className="text-dim/50">·</span>
            <span className="flex items-center gap-1">
              built with
              <span className="text-neon animate-pulse-glow">&#9829;</span>
              and too much coffee
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}
