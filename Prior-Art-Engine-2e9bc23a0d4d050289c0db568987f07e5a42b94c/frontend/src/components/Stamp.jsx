import React from "react";

export default function Stamp({ pct }) {
  const tier = pct >= 60 ? "high" : pct >= 35 ? "mid" : "low";
  const word = pct >= 60 ? "CLOSE MATCH" : pct >= 35 ? "PARTIAL MATCH" : "WEAK MATCH";
  return (
    <div className={`stamp stamp-${tier}`} title={`${pct.toFixed(1)}% fused similarity`}>
      {pct.toFixed(1)}% &middot; {word}
    </div>
  );
}
