export default function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Dot grid */}
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            'radial-gradient(circle, #e8e6e3 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />

      {/* Radial gradient fade */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,#07070a_70%)]" />

      {/* Glowing waypoints */}
      <div className="absolute top-1/4 left-1/4 w-2 h-2 rounded-full bg-neon/40 animate-pulse-glow" />
      <div
        className="absolute top-1/3 right-1/3 w-1.5 h-1.5 rounded-full bg-amber/40 animate-pulse-glow"
        style={{ animationDelay: '1s' }}
      />
      <div
        className="absolute bottom-1/3 left-1/2 w-2 h-2 rounded-full bg-ice/30 animate-pulse-glow"
        style={{ animationDelay: '2s' }}
      />
      <div
        className="absolute top-2/3 right-1/4 w-1 h-1 rounded-full bg-phantom/40 animate-pulse-glow"
        style={{ animationDelay: '0.5s' }}
      />
      <div
        className="absolute top-1/2 left-1/6 w-1.5 h-1.5 rounded-full bg-neon/30 animate-pulse-glow"
        style={{ animationDelay: '1.5s' }}
      />

      {/* Faint connection lines */}
      <svg className="absolute inset-0 w-full h-full opacity-[0.04]">
        <line x1="25%" y1="25%" x2="67%" y2="33%" stroke="#00ff88" strokeWidth="0.5" />
        <line x1="67%" y1="33%" x2="50%" y2="67%" stroke="#00ff88" strokeWidth="0.5" />
        <line x1="50%" y1="67%" x2="75%" y2="67%" stroke="#ffb800" strokeWidth="0.5" />
      </svg>
    </div>
  )
}
