import NavBar from './components/NavBar'
import Hero from './sections/Hero'
import Pipeline from './sections/Pipeline'
import Config from './sections/Config'
import QuestCards from './sections/QuestCards'
import WhyThisHits from './sections/WhyThisHits'
import TechFlex from './sections/TechFlex'
import FooterCTA from './sections/FooterCTA'

export default function App() {
  return (
    <div className="min-h-screen bg-void text-bone overflow-x-hidden">
      <NavBar />
      <Hero />
      <Pipeline />
      <Config />
      <QuestCards />
      <WhyThisHits />
      <TechFlex />
      <FooterCTA />
    </div>
  )
}
