import React from "react";

export default function ArmDCard({ armD }) {
  if (!armD.extraction) {
    if (armD.error && !armD.error.startsWith("GEMINI_API_KEY is not set")) {
      return <div className="warning-banner">⚠️ ARM D skipped: {armD.error}</div>;
    }
    return null;
  }

  return (
    <div className="armd-card">
      <div className="armd-label">🤖 ARM D · Gemini 2.5 Flash — Problem / Method Extraction</div>
      <div className="armd-field-label">Problem</div>
      <div className="armd-field-value">{armD.extraction.Problem}</div>
      <div className="armd-field-label">Method</div>
      <div className="armd-field-value">{armD.extraction.Method}</div>
    </div>
  );
}
