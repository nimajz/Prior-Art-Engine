import React from "react";

export default function HighlightedAbstract({ sentenceView, label, isPatent, highlightThresholdPct }) {
  if (!sentenceView) {
    return (
      <div className={isPatent ? "abstract-card-patent" : ""}>
        <div className="abstract-label">{label}</div>
        <div className="abstract-text">
          <span style={{ color: "var(--faint)", fontStyle: "italic" }}>No abstract available.</span>
        </div>
      </div>
    );
  }

  const { sentences, highlight_count, best_sentence, best_similarity } = sentenceView;

  return (
    <>
      <div className="abstract-label">{label}</div>
      <div className="abstract-text">
        {sentences.map((s, i) => (
          <React.Fragment key={i}>
            <span className={s.highlighted ? "sent-hl" : "sent-plain"}>{s.text}</span>{" "}
          </React.Fragment>
        ))}
      </div>
      <div className="highlight-legend">
        <span className="legend-swatch" />
        {highlight_count > 0
          ? `${highlight_count} sentence${highlight_count !== 1 ? "s" : ""} above ${highlightThresholdPct}% similarity`
          : `No sentences exceeded the ${highlightThresholdPct}% threshold`}
      </div>

      {best_sentence && (
        <div className={`best-sentence-block ${isPatent ? "is-patent" : ""}`}>
          <div className="best-sentence-head">
            <span>🎯</span>
            <span className="best-sentence-tag">
              {isPatent ? "Most similar claim sentence" : "Most similar sentence to your input"}
            </span>
            <span className="best-sentence-sim">{(best_similarity * 100).toFixed(1)}% similarity</span>
          </div>
          <div className="best-sentence-text">{best_sentence}</div>
        </div>
      )}
    </>
  );
}
