import React from "react";

export default function PatentDiagnosticsPanel({ patent }) {
  const allOk = patent.diagnostics.every((d) => d.status_code === 200);

  return (
    <div className="diag-panel">
      <strong style={{ color: "var(--amber)" }}>🗂️ ARM PV Debug — PatentsView v1 API</strong>{" "}
      {allOk ? (
        <span style={{ color: "var(--moss)", fontWeight: 700 }}>✅ API OK</span>
      ) : (
        <span style={{ color: "var(--amber)", fontWeight: 700 }}>⚠️ API ERRORS</span>
      )}
      <div style={{ marginTop: 6, color: "var(--muted)" }}>
        Raw hits before dedup: <strong>{patent.raw_hit_count}</strong> · After dedup &amp; parse:{" "}
        <strong>{patent.after_dedup_count}</strong> · After CE rerank: <strong>{patent.after_rerank_count}</strong>
      </div>
      <table className="diag-table">
        <thead>
          <tr>
            <th>Keyphrase</th>
            <th>HTTP</th>
            <th>Error</th>
            <th style={{ textAlign: "right" }}>Hits</th>
          </tr>
        </thead>
        <tbody>
          {patent.diagnostics.map((d, i) => (
            <tr key={i}>
              <td className="mono">{(d.phrase || "?").slice(0, 40)}</td>
              <td className="mono" style={{ color: d.status_code === 200 ? "var(--moss)" : "var(--amber)" }}>
                HTTP {d.status_code}
              </td>
              <td>{d.error || "—"}</td>
              <td style={{ textAlign: "right" }} className="mono">
                {d.hit_count} hits
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
