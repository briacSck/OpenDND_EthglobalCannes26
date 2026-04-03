import ScrollReveal from '../components/ScrollReveal'
import ParticleField from '../components/ParticleField'

const steps = [
  {
    fn: 'scan_city()',
    label: 'Read the map',
    desc: 'Researches what makes your city / neighborhood actually special. Local events, hidden spots, cultural landmarks, seasonal context. Not generic "top 10" lists.',
    color: 'text-coral',
    accent: '#ff6b4a',
    dotBg: 'bg-coral',
  },
  {
    fn: 'read_vibe()',
    label: 'Match the energy',
    desc: 'Takes your goals, mood, crew size, and comfort zone. Culture-maxx? Spy-game date? Solo touch-grass? It calibrates the entire run to how you actually want to feel.',
    color: 'text-indigo',
    accent: '#7c5cff',
    dotBg: 'bg-indigo',
  },
  {
    fn: 'assemble_run()',
    label: 'Draft the arc',
    desc: 'Builds the quest structure. Checks budget, timing, distance between stops, transit, opening hours. Every checkpoint is reachable, affordable, and worth it. No wasted steps.',
    color: 'text-cyan',
    accent: '#00e5ff',
    dotBg: 'bg-cyan',
  },
  {
    fn: 'ship_quest()',
    label: 'Deploy the adventure',
    desc: 'Delivers a playable quest with named checkpoints, directions, time estimates, and optional side quests. The dungeon master has spoken. Go touch grass.',
    color: 'text-gold',
    accent: '#ffd84a',
    dotBg: 'bg-gold',
  },
]

export default function Pipeline() {
  return (
    <section id="pipeline" className="relative py-28 px-6 bg-surface/50 overflow-hidden">
      {/* Particle background */}
      <ParticleField count={45} />

      {/* Top fade */}
      <div className="absolute top-0 inset-x-0 h-24 bg-gradient-to-b from-base to-transparent" />
      <div className="absolute bottom-0 inset-x-0 h-24 bg-gradient-to-t from-base to-transparent" />

      <div className="relative z-10 max-w-5xl mx-auto">
        <ScrollReveal>
          <div className="text-center mb-20">
            <span className="inline-block font-mono text-xs text-indigo/70 tracking-widest uppercase mb-4">
              // quest_pipeline
            </span>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-bone mb-4">
              How the quest gets built
            </h2>
            <p className="text-muted max-w-xl mx-auto">
              City intelligence + life design + DM orchestration.
              <br />
              Not vibes. Not guesswork. An actual pipeline.
            </p>
          </div>
        </ScrollReveal>

        {/* Timeline layout */}
        <div className="relative">
          {/* Vertical line — center on md+, left on mobile */}
          <div className="absolute left-6 md:left-1/2 md:-translate-x-px top-0 bottom-0 w-0.5 bg-gradient-to-b from-coral/40 via-indigo/30 to-gold/40" />

          {steps.map((step, i) => {
            const isRight = i % 2 === 0
            return (
              <ScrollReveal
                key={step.fn}
                delay={i * 0.15}
                direction={isRight ? 'right' : 'left'}
              >
                <div className={`relative flex items-start gap-6 mb-16 last:mb-0 md:gap-0 ${
                  isRight ? 'md:flex-row' : 'md:flex-row-reverse'
                }`}>
                  {/* Timeline dot */}
                  <div className="absolute left-6 md:left-1/2 -translate-x-1/2 w-4 h-4 rounded-full border-2 border-base z-10 mt-2"
                    style={{ backgroundColor: step.accent }}
                  >
                    <div className="absolute inset-0 rounded-full animate-pulse-glow"
                      style={{ backgroundColor: step.accent, opacity: 0.5 }}
                    />
                  </div>

                  {/* Spacer for mobile left offset */}
                  <div className="w-12 shrink-0 md:hidden" />

                  {/* Content card */}
                  <div className={`flex-1 md:w-[calc(50%-2rem)] ${
                    isRight ? 'md:pr-12' : 'md:pl-12'
                  }`}>
                    <div className="p-6 rounded-xl bg-surface/80 border border-elevated/30 backdrop-blur-sm hover:border-elevated/60 transition-all duration-300"
                      style={{ boxShadow: `0 0 40px ${step.accent}08` }}
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <span className="font-mono text-xs text-dim">0{i + 1}</span>
                        <span className={`font-mono text-sm font-semibold ${step.color}`}>
                          {step.fn}
                        </span>
                      </div>
                      <h3 className="text-xl font-bold text-bone mb-2">
                        {step.label}
                      </h3>
                      <p className="text-sm text-muted leading-relaxed">
                        {step.desc}
                      </p>
                    </div>
                  </div>

                  {/* Empty half for desktop */}
                  <div className="hidden md:block md:w-[calc(50%-2rem)]" />
                </div>
              </ScrollReveal>
            )
          })}
        </div>

        {/* Pipeline output terminal */}
        <ScrollReveal delay={0.5}>
          <div className="mt-16 mx-auto max-w-2xl p-5 rounded-xl bg-base/90 border border-elevated/20 font-mono text-xs backdrop-blur-sm">
            <div className="flex items-center gap-2 text-dim mb-3">
              <span className="text-coral">$</span> opendnd run --city="Cannes" --vibe="culture-maxx"
            </div>
            <div className="space-y-1 text-dim">
              <div><span className="text-coral">&#10003;</span> city scanned &middot; 47 POIs indexed</div>
              <div><span className="text-indigo">&#10003;</span> vibe matched &middot; culture + discovery weighted</div>
              <div><span className="text-cyan">&#10003;</span> arc assembled &middot; 5 checkpoints, 3h42m runtime</div>
              <div><span className="text-gold">&#10003;</span> quest shipped &middot; <span className="text-neon">ready to deploy</span></div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
