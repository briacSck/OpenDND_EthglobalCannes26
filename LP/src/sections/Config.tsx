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
  color = 'coral',
}: {
  label: string
  options: string[]
  color?: string
}) {
  const [selected, setSelected] = useState(options[0])

  const colorMap: Record<string, { active: string; ring: string }> = {
    coral: { active: 'bg-coral/15 border-coral/40 text-coral', ring: 'ring-coral/20' },
    indigo: { active: 'bg-indigo/15 border-indigo/40 text-indigo', ring: 'ring-indigo/20' },
    cyan: { active: 'bg-cyan/15 border-cyan/40 text-cyan', ring: 'ring-cyan/20' },
    gold: { active: 'bg-gold/15 border-gold/40 text-gold', ring: 'ring-gold/20' },
    ember: { active: 'bg-ember/15 border-ember/40 text-ember', ring: 'ring-ember/20' },
    neon: { active: 'bg-neon/15 border-neon/40 text-neon', ring: 'ring-neon/20' },
  }

  const colors = colorMap[color] || colorMap.coral

  return (
    <div>
      <label className="block font-mono text-xs text-dim mb-2 uppercase tracking-wider">
        {label}
      </label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => setSelected(opt)}
            className={`relative px-3 py-1.5 rounded-lg border font-mono text-xs transition-all duration-200 cursor-pointer ${
              selected === opt
                ? `${colors.active} ring-1 ${colors.ring}`
                : 'border-elevated/40 text-muted hover:border-elevated hover:text-bone'
            }`}
          >
            {selected === opt && (
              <motion.div
                layoutId={`config-${label}`}
                className="absolute inset-0 rounded-lg bg-white/5"
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
      <label className="block font-mono text-xs text-dim mb-2 uppercase tracking-wider">
        city
      </label>
      <div
        className={`relative flex items-center border rounded-lg transition-all duration-200 ${
          focused
            ? 'border-coral/40 ring-1 ring-coral/20 bg-coral/5'
            : 'border-elevated/40 bg-base/50'
        }`}
      >
        <span className="pl-3 text-dim font-mono text-sm">&gt;</span>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          className="flex-1 bg-transparent px-2 py-2.5 font-mono text-sm text-coral outline-none placeholder:text-dim/50"
          placeholder="enter city..."
        />
        <AnimatePresence>
          {value && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="pr-3 text-coral/60 text-xs font-mono"
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
    <section id="config" className="relative py-28 px-6 overflow-hidden">
      <div className="max-w-4xl mx-auto">
        <ScrollReveal>
          <div className="text-center mb-14">
            <span className="inline-block font-mono text-xs text-gold/70 tracking-widest uppercase mb-4">
              // quest.params
            </span>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-bone mb-4">
              Build config for your life
            </h2>
            <p className="text-muted max-w-lg mx-auto">
              Every quest is generated from your actual constraints.
              <br />
              Think character creation screen, but for your weekend.
            </p>
          </div>
        </ScrollReveal>

        <ScrollReveal delay={0.15}>
          <div className="relative">
            {/* Glassmorphism glow — layered blobs */}
            <div className="absolute -inset-8 pointer-events-none">
              <div className="absolute top-0 left-1/4 w-64 h-64 bg-indigo/15 rounded-full blur-[80px]" />
              <div className="absolute bottom-0 right-1/4 w-48 h-48 bg-coral/12 rounded-full blur-[60px]" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 bg-cyan/8 rounded-full blur-[100px]" />
            </div>

            <div className="relative bg-surface/60 border border-indigo/10 rounded-2xl p-8 backdrop-blur-xl shadow-2xl shadow-indigo/5">
              {/* Header */}
              <div className="flex items-center gap-2 mb-6 pb-4 border-b border-elevated/30">
                <div className="w-3 h-3 rounded-full bg-coral/70" />
                <div className="w-3 h-3 rounded-full bg-gold/70" />
                <div className="w-3 h-3 rounded-full bg-neon/70" />
                <span className="ml-3 font-mono text-xs text-dim">
                  new_quest.config
                </span>
                <span className="ml-auto font-mono text-xs text-dim/50">
                  v0.1.0
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <CityInput />
                <ConfigToggle label="vibe" options={vibeOptions} color="indigo" />
                <ConfigToggle label="objective" options={objectiveOptions} color="cyan" />
                <ConfigToggle label="party" options={partyOptions} color="gold" />
                <ConfigToggle label="time" options={timeOptions} color="coral" />
                <ConfigToggle label="budget" options={budgetOptions} color="neon" />
              </div>

              {/* Generate button */}
              <div className="mt-8 pt-6 border-t border-elevated/30 flex items-center justify-between">
                <span className="font-mono text-xs text-dim flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-neon animate-pulse-glow" />
                  all params set
                </span>
                <button className="px-6 py-2.5 bg-coral text-white font-mono text-sm font-semibold rounded-lg hover:shadow-[0_0_24px_rgba(255,107,74,0.3)] transition-all duration-300 cursor-pointer">
                  instantiate quest &rarr;
                </button>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
