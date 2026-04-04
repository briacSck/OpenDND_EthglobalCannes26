import NavBar from './components/NavBar'
import Hero from './sections/Hero'
import Config from './sections/Config'
import QuestCards from './sections/QuestCards'

export default function App() {
  return (
    <div className="min-h-screen bg-cream text-navy overflow-x-hidden">
      <NavBar />
      <Hero />
      <Config />
      <QuestCards />

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-sand/40">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-1">
            <span className="font-display font-bold text-lg text-terra">Open</span>
            <span className="font-display font-bold text-lg text-navy">D&D</span>
            <span className="text-muted font-mono text-xs ml-2">quest orchestrator</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted font-mono">
            <span>ETHGlobal Cannes 2026</span>
          </div>
          <a
            href="#"
            className="px-5 py-2.5 bg-terra text-cream text-sm font-semibold rounded-full hover:bg-terra-deep transition-colors"
          >
            Download the app
          </a>
        </div>
      </footer>
    </div>
  )
}
