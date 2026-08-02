import React from "react";

export default function PipelineDebugPanel({ data }) {
  const { classifier, yake_keyphrases, keyword_fallback_terms, concepts, retrieval, arm_d } = data;

  return (
    <div className="debug-block">
      <div className="section-eyebrow">Pipeline debug decomposition</div>

      <div className="classifier-strip">
        <span>words={classifier.word_count}</span>
        <span>acronym_density={classifier.acronym_density.toFixed(2)}</span>
        <span>domain_hits={classifier.domain_hit_count}</span>
        <span style={{ fontWeight: 700, color: classifier.force_keyword_arm ? "var(--seal)" : "var(--faint)" }}>
          {classifier.force_keyword_arm ? "⚡ ARM C FORCED" : "ARM C conditional"}
        </span>
      </div>

      <div className="debug-card">
        <div className="debug-card-title">Layer 1 · YAKE keyphrases ({yake_keyphrases.length})</div>
        <div className="pill-row">
          {yake_keyphrases.map((p, i) => (
            <span className="pill pill-yake" key={i}>
              {p}
            </span>
          ))}
        </div>
      </div>

      <div className="debug-card">
        <div className="debug-card-title">ARM C · Precision keywords</div>
        <div className="pill-row">
          {keyword_fallback_terms.map((w, i) => (
            <span className="pill pill-kw" key={i}>
              {w}
            </span>
          ))}
        </div>
      </div>

      {concepts.length > 0 ? (
        <div className="debug-card">
          <div className="debug-card-title">Layer 2+3 · OpenAlex concept graph (fused ranking)</div>
          <table className="concept-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Concept</th>
                <th>ID</th>
                <th style={{ textAlign: "right" }}>Citations</th>
              </tr>
            </thead>
            <tbody>
              {concepts.map((c, i) => (
                <tr key={c.id}>
                  <td>#{i + 1}</td>
                  <td>{c.name}</td>
                  <td className="mono">{c.id}</td>
                  <td style={{ textAlign: "right" }}>{c.cited_by.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="warning-banner">
          ⚠️ OpenAlex returned no concepts — ARM C (keyword fallback) is the primary retrieval arm.
        </div>
      )}

      <div className="debug-card">
        <div className="debug-card-title">
          📦 {retrieval.total_after_merge} unique candidates after dedup
        </div>
        <div className="arm-badges">
          <span className="arm-badge arm-a">ARM A concept</span> {retrieval.source_breakdown.concept}
          <span className="arm-badge arm-b">ARM B full-text</span> {retrieval.source_breakdown.fulltext}
          <span className="arm-badge arm-c">ARM C keyword</span> {retrieval.source_breakdown.keyword}
          <span style={{ color: "var(--faint)", fontSize: 11 }}>(always active)</span>
          <span className="arm-badge arm-d">ARM D Gemini</span>
          {arm_d.extraction ? (
            <span style={{ color: "var(--violet)", fontSize: 11 }}>
              {arm_d.new_candidate_count} new candidates added
            </span>
          ) : (
            <span style={{ color: "var(--faint)", fontSize: 11 }}>skipped</span>
          )}
        </div>
        {retrieval.auto_supplement_triggered && (
          <div className="warning-banner" style={{ marginTop: 10 }}>
            ⚠️ Auto-supplement triggered — top bi-encoder score was only{" "}
            {(retrieval.max_bi_score * 100).toFixed(1)}%. ARM C was added to boost pool quality.
          </div>
        )}
        <div style={{ marginTop: 8, fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--muted)" }}>
          Pruned to {retrieval.top_candidates_for_rerank} top candidates for cross-encoder reranking · max
          bi-score {(retrieval.max_bi_score * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
}
