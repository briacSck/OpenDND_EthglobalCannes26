export default function AuroraBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Base darkening layer */}
      <div className="absolute inset-0 bg-base" />

      {/* Aurora blob 1 — indigo, top-left drift */}
      <div
        className="absolute w-[800px] h-[800px] rounded-full opacity-20 blur-[120px]"
        style={{
          background: 'radial-gradient(circle, #7c5cff 0%, transparent 70%)',
          top: '-15%',
          left: '-10%',
          animation: 'aurora-shift-1 18s ease-in-out infinite',
        }}
      />

      {/* Aurora blob 2 — coral, center-right drift */}
      <div
        className="absolute w-[600px] h-[600px] rounded-full opacity-15 blur-[100px]"
        style={{
          background: 'radial-gradient(circle, #ff6b4a 0%, transparent 70%)',
          top: '10%',
          right: '-5%',
          animation: 'aurora-shift-2 22s ease-in-out infinite',
        }}
      />

      {/* Aurora blob 3 — cyan, bottom drift */}
      <div
        className="absolute w-[700px] h-[700px] rounded-full opacity-10 blur-[140px]"
        style={{
          background: 'radial-gradient(circle, #00e5ff 0%, transparent 70%)',
          bottom: '-20%',
          left: '20%',
          animation: 'aurora-shift-3 25s ease-in-out infinite',
        }}
      />

      {/* Subtle gold wisp */}
      <div
        className="absolute w-[400px] h-[400px] rounded-full opacity-[0.08] blur-[80px]"
        style={{
          background: 'radial-gradient(circle, #ffd84a 0%, transparent 70%)',
          top: '40%',
          left: '50%',
          animation: 'aurora-shift-2 30s ease-in-out infinite reverse',
        }}
      />

      {/* Top-down vignette for readability */}
      <div className="absolute inset-0 bg-gradient-to-b from-base/40 via-transparent to-base/80" />
    </div>
  )
}
