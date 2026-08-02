import React from "react";

export default function GlobalReportSection({ globalReport, enabled }) {
  return (
    <div className="global-report-section">
      <h2 className="global-report-title">⚖️ Comprehensive Prior-Art Distinctiveness Report</h2>

      <div className="disclaimer-box">
        ⚠️ <strong>This is NOT a patentability or legal opinion.</strong> It is a single Gemini-assisted
        textual comparison between your input and the combined titles/abstracts of the top documents this
        engine retrieved. It does not consider patent claims, prosecution history, or any prior art outside
        what is shown above — only a fraction of the real-world landscape. Consult a registered patent
        attorney or agent before making any filing, investment, or disclosure decision.
      </div>

      {!enabled ? (
        <div className="report-unavailable">
          Global Patentability &amp; Novelty Report is disabled. Enable it in search settings to generate a
          consolidated assessment.
        </div>
      ) : !globalReport ? (
        <div className="report-unavailable">📭 No retrieved documents are available to assess.</div>
      ) : globalReport.reason === "no_documents" ? (
        <div className="report-unavailable">
          📭 No retrieved documents are available to assess. Run a search that returns at least one academic
          or patent result first.
        </div>
      ) : !globalReport.available ? (
        <div className="report-unavailable">
          {String(globalReport.error || "").includes("GEMINI_API_KEY")
            ? "🔑 Global report unavailable — GEMINI_API_KEY is not configured."
            : `⚠️ Global report unavailable: ${globalReport.error || "Unknown error."}`}
          <div style={{ fontSize: 11.5, marginTop: 6 }}>
            All retrieval and ranking results above are unaffected — only this summary report failed to
            generate.
          </div>
        </div>
      ) : (
        <>
          <div className="report-source-caption">
            Assessed against the top {globalReport.n_total} retrieved document(s) by fused score —{" "}
            {globalReport.n_academic} academic paper(s), {globalReport.n_patent} patent(s).
          </div>

          <div className="report-metrics">
            <MetricCard label="🎯 Global Utility" value={globalReport.report.global_utility_score} />
            <MetricCard label="✨ Global Novelty" value={globalReport.report.global_novelty_score} />
            <MetricCard
              label="🧩 Combination Non-Obviousness"
              value={globalReport.report.global_combination_score}
            />
          </div>

          <ReasonBlock label="🎯 Global Utility — Reasoning" text={globalReport.report.global_utility_reason} />
          <ReasonBlock label="✨ Global Novelty — Reasoning" text={globalReport.report.global_novelty_reason} />
          <ReasonBlock
            label="🧩 Combination Non-Obviousness — Reasoning"
            text={globalReport.report.global_combination_reason}
          />
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {value}
        <span className="of5">/5</span>
      </div>
    </div>
  );
}

function ReasonBlock({ label, text }) {
  return (
    <div className="reason-block">
      <div className="reason-label">{label}</div>
      <div className="reason-text">{text}</div>
    </div>
  );
}
