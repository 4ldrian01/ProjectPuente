/**
 * VintaIcon.jsx — Vinta boat icon with purple/pink and yellow sail colors
 */

export default function VintaIcon({ className = "w-8 h-8" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Main sail - gradient from magenta to yellow */}
      <path
        d="M32 8L48 44H16L32 8Z"
        fill="url(#vintaSailGradient)"
      />
      {/* Secondary sail accent */}
      <path
        d="M32 14L42 40H22L32 14Z"
        fill="url(#vintaSailAccent)"
        opacity="0.8"
      />
      {/* Boat hull */}
      <path
        d="M12 48C12 48 18 52 32 52C46 52 52 48 52 48L48 44H16L12 48Z"
        fill="#D946EF"
      />
      {/* Boat base */}
      <ellipse
        cx="32"
        cy="52"
        rx="20"
        ry="4"
        fill="#FACC15"
        opacity="0.9"
      />
      {/* Mast */}
      <rect
        x="31"
        y="6"
        width="2"
        height="46"
        fill="#F5F5F5"
        rx="1"
      />
      {/* Flag at top */}
      <path
        d="M33 6L40 10L33 14V6Z"
        fill="#FACC15"
      />
      
      <defs>
        <linearGradient id="vintaSailGradient" x1="32" y1="8" x2="32" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FACC15" />
          <stop offset="50%" stopColor="#D946EF" />
          <stop offset="100%" stopColor="#D946EF" />
        </linearGradient>
        <linearGradient id="vintaSailAccent" x1="32" y1="14" x2="32" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FACC15" />
          <stop offset="100%" stopColor="#D946EF" />
        </linearGradient>
      </defs>
    </svg>
  )
}
