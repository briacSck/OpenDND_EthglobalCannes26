import ScrollReveal from '../components/ScrollReveal'

const quests = [
  {
    name: 'Cannes Culture Maxxoor',
    city: 'Cannes',
    duration: '4h',
    party: 'solo',
    vibe: 'culture-maxx',
    vibeColor: 'bg-gold/10 text-gold border-gold/30',
    desc: 'Museum speed-run at La Malmaison \u2192 hidden gallery in Le Suquet \u2192 croisette photo-lore checkpoint \u2192 secret cinema screening \u2192 rooftop aperitif with sea view.',
    checkpoints: 5,
    difficulty: 'Intermediate',
    diffColor: 'text-gold',
  },
  {
    name: 'Spy Game: Date Night Protocol',
    city: 'Paris',
    duration: '3h',
    party: 'duo',
    vibe: 'spy-game',
    vibeColor: 'bg-sea/10 text-sea border-sea/30',
    desc: 'Dead drop at a bookshop in the Marais \u2192 coded message at a speakeasy \u2192 rendezvous at a candlelit wine bar \u2192 final debrief on Pont des Arts. Romance with opsec.',
    checkpoints: 4,
    difficulty: 'Advanced',
    diffColor: 'text-sea-deep',
  },
  {
    name: 'Touch Grass (Legendary)',
    city: 'Any city',
    duration: '5h',
    party: 'solo',
    vibe: 'touch-grass',
    vibeColor: 'bg-olive/10 text-olive border-olive/30',
    desc: 'Dawn trail run to a viewpoint \u2192 cold plunge at nearest body of water \u2192 farmers market checkpoint \u2192 cook what you bought \u2192 sunset stretch at a park you\'ve never been to.',
    checkpoints: 5,
    difficulty: 'Hard',
    diffColor: 'text-terra',
  },
  {
    name: 'NPC \u2192 Party Member',
    city: 'Any city',
    duration: '2h',
    party: 'squad',
    vibe: 'social-arc',
    vibeColor: 'bg-terra/10 text-terra border-terra/30',
    desc: 'Show up at a community event \u2192 complete a shared challenge with strangers \u2192 group food quest at a local spot \u2192 exchange lore (contacts). You walked in solo, you leave with a party.',
    checkpoints: 4,
    difficulty: 'Beginner',
    diffColor: 'text-olive',
  },
]

export default function QuestCards() {
  return (
    <section id="quests" className="relative py-16 sm:py-28 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto">
        <ScrollReveal>
          <div className="text-center mb-10 sm:mb-16">
            <span className="inline-block font-mono text-[10px] sm:text-xs text-sea/70 tracking-widest uppercase mb-3 sm:mb-4">
              // sample_quests
            </span>
            <h2 className="text-2xl sm:text-4xl md:text-5xl font-display font-bold tracking-tight text-navy mb-3 sm:mb-4">
              Quests that actually go hard
            </h2>
            <p className="text-muted text-sm sm:text-base max-w-lg mx-auto">
              Full narrative arcs with checkpoints, lore, and a reason to leave the house.
            </p>
          </div>
        </ScrollReveal>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
          {quests.map((q, i) => (
            <ScrollReveal key={q.name} delay={i * 0.1}>
              <div className="group relative h-full p-5 sm:p-6 rounded-2xl bg-parchment/50 border border-sand/30 hover:border-terra/20 transition-all duration-300 hover:shadow-lg hover:shadow-terra/5">
                <div className="flex items-start justify-between mb-3 sm:mb-4 gap-3">
                  <div className="min-w-0">
                    <h3 className="text-base sm:text-lg font-bold text-navy mb-1 group-hover:text-terra transition-colors">
                      {q.name}
                    </h3>
                    <div className="flex items-center gap-2 text-[10px] sm:text-xs text-muted font-mono">
                      <span>{q.city}</span>
                      <span className="text-sand">&middot;</span>
                      <span>{q.duration}</span>
                      <span className="text-sand">&middot;</span>
                      <span>{q.party}</span>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 px-2 sm:px-2.5 py-1 rounded-full border text-[10px] sm:text-xs font-mono ${q.vibeColor}`}
                  >
                    {q.vibe}
                  </span>
                </div>

                <p className="text-xs sm:text-sm text-muted leading-relaxed mb-4 sm:mb-5">
                  {q.desc}
                </p>

                <div className="flex items-center gap-4 pt-3 sm:pt-4 border-t border-sand/30 text-[10px] sm:text-xs font-mono">
                  <span className="text-muted">
                    <span className="text-navy">{q.checkpoints}</span> checkpoints
                  </span>
                  <span className="text-muted">
                    difficulty: <span className={q.diffColor}>{q.difficulty}</span>
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
