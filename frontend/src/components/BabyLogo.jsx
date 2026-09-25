export default function BabyLogo({ compact = false, className = '' }) {
  return (
    <span className={`babyWordmarkFrame ${compact ? 'compact' : ''}`}>
      <img
        className={`babyWordmark ${compact ? 'compact' : ''} ${className}`.trim()}
        src="/baby-logo-transparent.png"
        alt="BABY Investment Research"
      />
    </span>
  );
}