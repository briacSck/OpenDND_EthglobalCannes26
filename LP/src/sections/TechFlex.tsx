import ScrollReveal from '../components/ScrollReveal'

const stack = [
  { label: 'agent_orchestration', desc: 'Multi-step AI pipeline. Not a single prompt. A coordinated system of agents that research, plan, validate, and assemble.', color: 'text-neon' },
  { label: 'city_research_loop', desc: 'Pulls real data on events, POIs, transit, hours, reviews. Context-aware, not a static database dump.', color: 'text-amber' },
  { label: 'constraint_solver', desc: 'Budget, distance, timing, group size — hard constraints get respected. No "just take a taxi" handwaving.', color: 'text-ice' },
  { label: 'adaptive_quest_logic', desc: 'Quests adjust to weather, time of day, and real-time availability. The arc bends but doesn\'t break.', color: 'text-phantom' },
  { label: 'checkpoint_system', desc: 'Each quest has named waypoints with directions, time windows, and optional side quests for overachievers.', color: 'text-ember' },
  { label: 'mobile_first', desc: 'Built for your pocket. GPS-aware, notification-ready, works offline once the quest is loaded.', color: 'text-neon' },
]

export default function TechFlex() {
  return (
    <section id="tech" className="relative py-28 px-6">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-20 bg-gradient-to-b from-transparent to-slate-light/30" />

      <div className="max-w-5xl mx-auto">
        <ScrollReveal>
          <div className="text-center mb-14">
            <span className="inline-block font-mono text-xs text-ice/70 tracking-widest uppercase mb-4">
              // under_the_hood
            </span>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-bone mb-4">
              Not fake magic
            </h2>
            <p className="text-muted max-w-lg mx-auto">
              Real orchestration. Real constraints. Real infrastructure.
              <br />
              Read the README if you don&rsquo;t believe us.
            </p>
          </div>
        </ScrollReveal>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {stack.map((s, i) => (
            <ScrollReveal key={s.label} delay={i * 0.08}>
              <div className="group p-5 rounded-xl bg-abyss/60 border border-slate-light/15 hover:border-slate-light/30 transition-all duration-300">
                <div className="flex items-center gap-2 mb-3">
                  <span className={`font-mono text-xs font-semibold ${s.color}`}>
                    {s.label}
                  </span>
                </div>
                <p className="text-sm text-muted leading-relaxed">
                  {s.desc}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>

        {/* Mini terminal */}
        <ScrollReveal delay={0.4}>
          <div className="mt-10 mx-auto max-w-xl p-4 rounded-xl bg-abyss/80 border border-slate-light/15 font-mono text-xs text-dim">
            <span className="text-neon">$</span> opendnd --version
            <br />
            <span className="text-bone">OpenD&D v0.1.0</span> — quest orchestrator
            <br />
            <span className="text-dim">agents: 4 | models: adaptive | constraints: hard | vibes: immaculate</span>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
