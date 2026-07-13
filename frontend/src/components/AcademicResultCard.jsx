import React from "react";
import Stamp from "./Stamp.jsx";
import HighlightedAbstract from "./HighlightedAbstract.jsx";

export default function AcademicResultCard({ result, showDebug, highlightThresholdPct }) {
  return (
    <div className="exhibit">
      <div className="exhibit-header">
        <div className="exhibit-top-row">
          <div>
            <div className="exhibit-rank">Exhibit #{result.rank}</div>
            <h3 className="exhibit-title">{result.title}</h3>
          </div>
          <Stamp pct={result.fused_pct} />
        </div>

        <div className="exhibit-meta">
          <span>📅 {result.date || "No date"}</span>
          {result.doi ? (
            <a href={result.doi} target="_blank" rel="noreferrer">
              {result.doi}
            </a>
          ) : (
            <span>No DOI available</span>
          )}
        </div>

        {result.concepts && result.concepts.length > 0 && (
          <div className="exhibit-concepts">
            {result.concepts.map((c, i) => (
              <span className="pill pill-concept" key={i}>
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
          label="Abstract · Semantic Highlight View"
          highlightThresholdPct={highlightThresholdPct}
        />
      </div>
    </div>
  );
}
