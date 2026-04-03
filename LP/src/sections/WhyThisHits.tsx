import { motion } from 'framer-motion'
import ScrollReveal from '../components/ScrollReveal'

const points = [
  {
    lead: 'Your weekend has terrible product management.',
    body: 'You keep defaulting to the same three restaurants and calling it a plan. OpenD&D turns "I should do something" into an actual mission with checkpoints and a narrative arc.',
  },
  {
    lead: 'Your city is an open world you\'re speedrunning on easy mode.',
    body: 'There are 200 things worth doing within 30 minutes of you right now. You\'ve tried 4 of them. The dungeon master has notes on all 200.',
  },
  {
    lead: 'Main character energy is a system, not a vibe.',
    body: 'Romanticizing your life doesn\'t happen by accident. It happens when someone designs the quest. That someone is now an AI agent with access to your city\'s entire map.',
  },
  {
    lead: 'Stop optimizing your screen time. Optimize your stories.',
    body: 'The best memories aren\'t planned on Google Maps at 11pm. They\'re orchestrated by something that actually understands timing, budget, distance, and what makes a day feel legendary.',
  },
]

export default function WhyThisHits() {
  return (
    <section className="relative py-28 px-6">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-20 bg-gradient-to-b from-transparent to-slate-light/30" />

      <div className="max-w-4xl mx-auto">
        <ScrollReveal>
          <div className="text-center mb-16">
            <span className="inline-block font-mono text-xs text-ember/70 tracking-widest uppercase mb-4">
              // why_this_hits
            </span>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-bone mb-4">
              Your life needs better quest design
            </h2>
            <p className="text-muted max-w-lg mx-auto">
              This isn&rsquo;t another recommendation engine.
              <br />
              It&rsquo;s the difference between browsing a menu and being handed a mission.
            </p>
          </div>
        </ScrollReveal>

        <div className="space-y-6">
          {points.map((p, i) => (
            <ScrollReveal key={i} delay={i * 0.1}>
              <motion.div
                whileHover={{ x: 4 }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                className="group relative pl-6 py-5 pr-6 rounded-xl border border-slate-light/10 hover:border-slate-light/30 bg-slate-dark/20 hover:bg-slate-dark/40 transition-all duration-300"
              >
                {/* Left accent bar */}
                <div className="absolute left-0 top-4 bottom-4 w-0.5 bg-gradient-to-b from-neon/60 to-neon/0 rounded-full" />

                <h3 className="text-base sm:text-lg font-semibold text-bone mb-2 leading-snug">
                  {p.lead}
                </h3>
                <p className="text-sm text-muted leading-relaxed">
                  {p.body}
                </p>
              </motion.div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  )
}
