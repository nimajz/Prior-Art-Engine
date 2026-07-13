import React from "react";
import Stamp from "./Stamp.jsx";
import HighlightedAbstract from "./HighlightedAbstract.jsx";

export default function PatentResultCard({ result, showDebug, highlightThresholdPct }) {
  return (
    <div className="exhibit">
      <div className="exhibit-header is-patent">
        <div className="exhibit-top-row">
          <div>
            <div className="exhibit-rank">
              Patent #{result.rank} &middot;{" "}
              <span className="pill pill-kw" style={{ marginLeft: 4 }}>
                USPTO &middot; PatentsView
              </span>
            </div>
            {result.publication_number && (
              <div style={{ marginTop: 6 }}>
                <span className="patent-number-chip">US{result.publication_number}</span>
              </div>
            )}
            <h3 className="exhibit-title patent-title">{result.title}</h3>
          </div>
          <Stamp pct={result.fused_pct} />
        </div>

        <div className="exhibit-meta">
          <span>📅 Published: {result.publication_date || "—"}</span>
          {result.google_patents_url && (
            <a href={result.google_patents_url} target="_blank" rel="noreferrer">
              View on Google Patents ↗
            </a>
          )}
        </div>

        {result.cpc_codes && result.cpc_codes.length > 0 && (
          <div className="exhibit-concepts">
            🏷
            {result.cpc_codes.slice(0, 4).map((c, i) => (
              <span className="cpc-chip" key={i}>
                {c}
              </span>
            ))}
          </div>
        )}

        {showDebug && (
          <div className="debug-scoreline">
            [Bi-Enc {result.bi_pct.toFixed(1)}% | Cross-Enc {result.ce_pct.toFixed(1)}%]
          </div>
        )}
      </div>

      <div className="exhibit-body">
        <HighlightedAbstract
          sentenceView={result.sentence_view}
          label="Patent Abstract · Semantic Highlight View"
          isPatent
          highlightThresholdPct={highlightThresholdPct}
        />
      </div>
    </div>
  );
}
