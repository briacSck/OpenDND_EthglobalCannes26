import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ScrollReveal from '../components/ScrollReveal'

const vibeOptions = ['culture-maxx', 'spy-game', 'touch-grass', 'chaos-mode', 'social-arc', 'chill-lore']
const objectiveOptions = ['explore', 'get fit', 'meet people', 'eat well', 'learn', 'go hard']
const partyOptions = ['solo', 'duo', 'squad']
const timeOptions = ['1h', '2h', '3h', '5h', 'full day']
const budgetOptions = ['$', '$$', '$$$', 'no cap']

function ConfigToggle({
  label,
  options,
  color = 'terra',
}: {
  label: string
  options: string[]
  color?: string
}) {
  const [selected, setSelected] = useState(options[0])

  const colorMap: Record<string, { active: string; ring: string }> = {
    terra: { active: 'bg-terra/10 border-terra/40 text-terra', ring: 'ring-terra/20' },
    sea: { active: 'bg-sea/10 border-sea/40 text-sea', ring: 'ring-sea/20' },
    gold: { active: 'bg-gold/15 border-gold/40 text-gold', ring: 'ring-gold/20' },
    olive: { active: 'bg-olive/10 border-olive/40 text-olive', ring: 'ring-olive/20' },
  }

  const colors = colorMap[color] || colorMap.terra

  return (
    <div>
      <label className="block font-mono text-[10px] sm:text-xs text-muted mb-2 uppercase tracking-wider">
        {label}
      </label>
      <div className="flex flex-wrap gap-1.5 sm:gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => setSelected(opt)}
            className={`relative px-2.5 sm:px-3 py-1.5 rounded-lg border font-mono text-[10px] sm:text-xs transition-all duration-200 cursor-pointer ${
              selected === opt
                ? `${colors.active} ring-1 ${colors.ring}`
                : 'border-sand/50 text-muted hover:border-sand hover:text-navy'
            }`}
          >
            {selected === opt && (
              <motion.div
                layoutId={`config-${label}`}
                className="absolute inset-0 rounded-lg bg-navy/[0.03]"
                transition={{ type: 'spring', duration: 0.4, bounce: 0.15 }}
              />
            )}
            <span className="relative">{opt}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function CityInput() {
  const [value, setValue] = useState('Cannes')
  const [focused, setFocused] = useState(false)

  return (
    <div>
      <label className="block font-mono text-[10px] sm:text-xs text-muted mb-2 uppercase tracking-wider">
        city
      </label>
      <div
        className={`relative flex items-center border rounded-lg transition-all duration-200 ${
          focused
            ? 'border-terra/40 ring-1 ring-terra/20 bg-terra/5'
            : 'border-sand/50 bg-cream/50'
        }`}
      >
        <span className="pl-3 text-muted font-mono text-sm">&gt;</span>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          className="flex-1 bg-transparent px-2 py-2.5 font-mono text-sm text-terra outline-none placeholder:text-muted/50"
          placeholder="enter city..."
        />
        <AnimatePresence>
          {value && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="pr-3 text-olive text-xs font-mono"
            >
              locked
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

export default function Config() {
  return (
    <section id="config" className="relative py-16 sm:py-28 px-4 sm:px-6">
      <div className="max-w-4xl mx-auto">
        <ScrollReveal>
          <div className="text-center mb-10 sm:mb-14">
            <span className="inline-block font-mono text-[10px] sm:text-xs text-terra/70 tracking-widest uppercase mb-3 sm:mb-4">
              // quest.params
            </span>
            <h2 className="text-2xl sm:text-4xl md:text-5xl font-display font-bold tracking-tight text-navy mb-3 sm:mb-4">
              Build config for your life
            </h2>
            <p className="text-muted text-sm sm:text-base max-w-lg mx-auto">
              Every quest is generated from your actual constraints.
              Think character creation screen, but for your weekend.
            </p>
          </div>
        </ScrollReveal>

        <ScrollReveal delay={0.15}>
          <div className="relative bg-parchment/60 border border-sand/40 rounded-2xl p-5 sm:p-8 backdrop-blur-sm shadow-xl shadow-navy/5">
            {/* Header */}
            <div className="flex items-center gap-2 mb-5 sm:mb-6 pb-3 sm:pb-4 border-b border-sand/40">
              <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-terra/60" />
              <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-gold/60" />
              <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-olive/60" />
              <span className="ml-2 sm:ml-3 font-mono text-[10px] sm:text-xs text-muted">
                new_quest.config
              </span>
              <span className="ml-auto font-mono text-[10px] sm:text-xs text-muted/50">
                v0.1.0
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 sm:gap-6">
              <CityInput />
              <ConfigToggle label="vibe" options={vibeOptions} color="sea" />
              <ConfigToggle label="objective" options={objectiveOptions} color="olive" />
              <ConfigToggle label="party" options={partyOptions} color="gold" />
              <ConfigToggle label="time" options={timeOptions} color="terra" />
              <ConfigToggle label="budget" options={budgetOptions} color="sea" />
            </div>

            {/* Generate button */}
            <div className="mt-6 sm:mt-8 pt-5 sm:pt-6 border-t border-sand/40 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <span className="font-mono text-[10px] sm:text-xs text-muted flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-olive animate-pulse-glow" />
                all params set
              </span>
              <a
                href="https://docs.google.com/forms/d/e/1FAIpQLSdUSYdRFqCImVTB5qUD0Lw27ss5pQKC8ufor-sS7vIw5iYq5A/viewform?usp=header"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto px-6 py-2.5 bg-terra text-cream font-mono text-sm font-semibold rounded-full hover:bg-terra-deep hover:shadow-lg hover:shadow-terra/20 transition-all duration-300 cursor-pointer active:scale-[0.97] inline-block text-center"
              >
                instantiate quest &rarr;
              </a>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
