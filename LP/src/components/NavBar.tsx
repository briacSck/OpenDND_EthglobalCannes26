import { useState, useEffect } from 'react'

export default function NavBar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? 'bg-cream/80 backdrop-blur-2xl shadow-sm shadow-terra/5 border-b border-sand/40'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#" className="flex items-center gap-1 group">
          <span className="font-display font-bold text-xl text-terra tracking-tight">
            Open
          </span>
          <span className="font-display font-bold text-xl text-navy tracking-tight">
            D&D
          </span>
        </a>

        <div className="hidden md:flex items-center gap-8 text-sm text-navy/60 font-medium">
          <a href="#pipeline" className="hover:text-terra transition-colors duration-200">
            How it works
          </a>
          <a href="#quests" className="hover:text-terra transition-colors duration-200">
            Quests
          </a>
          <a href="#config" className="hover:text-terra transition-colors duration-200">
            Configure
          </a>
          <a href="#tech" className="hover:text-terra transition-colors duration-200">
            Under the hood
          </a>
        </div>

        <a
          href="#cta"
          className="px-5 py-2 bg-terra text-cream text-sm font-semibold rounded-full hover:bg-terra-deep hover:shadow-lg hover:shadow-terra/20 transition-all duration-300"
        >
          Launch quest
        </a>
      </div>
    </nav>
  )
}
