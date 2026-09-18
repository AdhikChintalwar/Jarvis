import React from 'react';

export default function BabyLogo({compact=false,className=''}) {
  return (
    <img
      className={`babyWordmark ${compact ? 'compact' : ''} ${className}`.trim()}
      src="/baby-logo.png"
      alt="BABY Investment Research"
    />
  );
}
