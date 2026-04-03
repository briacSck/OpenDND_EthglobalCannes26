import ScrollReveal from '../components/ScrollReveal'

const quests = [
  {
    name: 'Cannes Culture Maxxoor',
    city: 'Cannes',
    duration: '4h',
    party: 'solo',
    vibe: 'culture-maxx',
    vibeColor: 'bg-amber/15 text-amber border-amber/30',
    desc: 'Museum speed-run at La Malmaison → hidden gallery in Le Suquet → croisette photo-lore checkpoint → secret cinema screening → rooftop aperitif with sea view. You leave knowing more than most locals.',
    checkpoints: 5,
    difficulty: 'Intermediate',
    diffColor: 'text-amber',
  },
  {
    name: 'Spy Game: Date Night Protocol',
    city: 'Paris',
    duration: '3h',
    party: 'duo',
    vibe: 'spy-game',
    vibeColor: 'bg-phantom/15 text-phantom border-phantom/30',
    desc: 'Dead drop at a bookshop in the Marais → coded message at a speakeasy → rendezvous at a candlelit wine bar → final debrief on Pont des Arts. Romance with opsec.',
    checkpoints: 4,
    difficulty: 'Advanced',
    diffColor: 'text-phantom',
  },
  {
    name: 'Touch Grass (Legendary)',
    city: 'Any city',
    duration: '5h',
    party: 'solo',
    vibe: 'touch-grass',
    vibeColor: 'bg-neon/15 text-neon border-neon/30',
    desc: 'Dawn trail run to a viewpoint → cold plunge at nearest body of water → farmers market checkpoint → cook what you bought → sunset stretch at a park you\'ve never been to. Main character energy: outdoors edition.',
    checkpoints: 5,
    difficulty: 'Hard',
    diffColor: 'text-ember',
  },
  {
    name: 'NPC → Party Member',
    city: 'Any city',
    duration: '2h',
    party: 'squad',
    vibe: 'social-arc',
    vibeColor: 'bg-ice/15 text-ice border-ice/30',
    desc: 'Show up at a community event → complete a shared challenge with strangers → group food quest at a local spot → exchange lore (contacts). You walked in solo, you leave with a party.',
    checkpoints: 4,
    difficulty: 'Beginner',
    diffColor: 'text-neon',
  },
]

export default function QuestCards() {
  return (
    <section id="quests" className="relative py-28 px-6">
      {/* Divider */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-20 bg-gradient-to-b from-transparent to-slate-light/30" />

      <div className="max-w-6xl mx-auto">
        <ScrollReveal>
          <div className="text-center mb-16">
            <span className="inline-block font-mono text-xs text-phantom/70 tracking-widest uppercase mb-4">
              // sample_quests
            </span>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-bone mb-4">
              Quests that actually go hard
            </h2>
            <p className="text-muted max-w-lg mx-auto">
              Not &ldquo;visit a museum&rdquo;. Not &ldquo;try a restaurant&rdquo;.
              <br />
              Full narrative arcs with checkpoints, lore, and a reason to leave the house.
            </p>
          </div>
        </ScrollReveal>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {quests.map((q, i) => (
            <ScrollReveal key={q.name} delay={i * 0.1}>
              <div className="group relative h-full p-6 rounded-xl bg-slate-dark/40 border border-slate-light/20 hover:border-slate-light/40 transition-all duration-300 hover:bg-slate-dark/60">
                {/* Header row */}
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-bone mb-1 group-hover:text-neon transition-colors">
                      {q.name}
                    </h3>
                    <div className="flex items-center gap-2 text-xs text-dim font-mono">
                      <span>{q.city}</span>
                      <span className="text-slate-light">·</span>
                      <span>{q.duration}</span>
                      <span className="text-slate-light">·</span>
                      <span>{q.party}</span>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 px-2.5 py-1 rounded-md border text-xs font-mono ${q.vibeColor}`}
                  >
                    {q.vibe}
                  </span>
                </div>

                {/* Description */}
                <p className="text-sm text-muted leading-relaxed mb-5">
                  {q.desc}
                </p>

                {/* Footer stats */}
                <div className="flex items-center gap-4 pt-4 border-t border-slate-light/15 text-xs font-mono">
                  <span className="text-dim">
                    <span className="text-bone">{q.checkpoints}</span> checkpoints
                  </span>
                  <span className="text-dim">
                    difficulty: <span className={q.diffColor}>{q.difficulty}</span>
                  </span>
                  <span className="ml-auto text-neon/50 opacity-0 group-hover:opacity-100 transition-opacity">
                    deploy &rarr;
                  </span>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  )
}
