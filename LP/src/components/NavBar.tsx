import { useState, useEffect } from 'react'

export default function NavBar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-base/70 backdrop-blur-2xl border-b border-indigo/10'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#" className="flex items-center gap-1.5 group">
          <span className="font-mono font-bold text-lg text-coral tracking-tight">
            Open
          </span>
          <span className="font-mono font-bold text-lg text-bone tracking-tight">
            D&D
          </span>
          <span className="w-2 h-2 rounded-full bg-coral animate-pulse-glow ml-1" />
        </a>

        <div className="hidden md:flex items-center gap-8 text-sm text-muted">
          <a href="#pipeline" className="hover:text-bone transition-colors duration-200">
            How it works
          </a>
          <a href="#quests" className="hover:text-bone transition-colors duration-200">
            Quests
          </a>
          <a href="#config" className="hover:text-bone transition-colors duration-200">
            Configure
          </a>
          <a href="#tech" className="hover:text-bone transition-colors duration-200">
            Under the hood
          </a>
        </div>

        <a
          href="#cta"
          className="px-4 py-2 bg-coral/10 border border-coral/25 text-coral text-sm font-mono rounded-lg hover:bg-coral/20 hover:border-coral/40 transition-all duration-200"
        >
          Launch quest
        </a>
      </div>
    </nav>
  )
}
