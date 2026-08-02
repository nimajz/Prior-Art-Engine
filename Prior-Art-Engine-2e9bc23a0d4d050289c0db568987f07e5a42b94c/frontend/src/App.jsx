import React, { useState } from "react";
import { runSearch } from "./api/client.js";
import ControlsPanel from "./components/ControlsPanel.jsx";
import PipelineDebugPanel from "./components/PipelineDebugPanel.jsx";
import ArmDCard from "./components/ArmDCard.jsx";
import AcademicResultCard from "./components/AcademicResultCard.jsx";
import PatentResultCard from "./components/PatentResultCard.jsx";
import PatentDiagnosticsPanel from "./components/PatentDiagnosticsPanel.jsx";
import GlobalReportSection from "./components/GlobalReportSection.jsx";

const DEFAULT_SETTINGS = {
  max_display: 5,
  effective_threshold: 25,
  highlight_threshold_pct: 78,
  show_debug: true,
  retrieval_mode: "Concept + Full-Text (Recommended)",
  enable_patent_search: true,
  enable_arm_d: true,
  enable_global_report: true,
};

export default function App() {
  const [idea, setIdea] = useState("");
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [showControls, setShowControls] = useState(false);
  const [activeTab, setActiveTab] = useState("academic");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!idea.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await runSearch({ idea, ...settings });
      setData(result);
    } catch (err) {
      setError(err.message || "Search failed.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <Masthead elapsed={data?.elapsed_s} />

      <main className="docket-layout">
        <form className="filing-card" onSubmit={handleSubmit}>
          <label className="filing-label" htmlFor="idea-input">
            Describe your research idea or technical system
          </label>
          <textarea
            id="idea-input"
            className="filing-textarea"
            placeholder={
              "Any style: formal abstract, casual description, bullet points, acronym-heavy, short phrase…\n\n" +
              "e.g. \"Evaluating toxic behavior in competitive multiplayer games using chat sentiment analysis and APM telemetry.\""
            }
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
          />
          <div className="filing-footer">
            <span className="filing-hint">
              Searched against OpenAlex (academic) and USPTO PatentsView (patent) prior art.
            </span>
            <button className="btn-submit" type="submit" disabled={loading || !idea.trim()}>
              {loading ? "Searching…" : "Search prior art"}
            </button>
          </div>

          <div className="controls-bar">
            <button
              type="button"
              className="controls-toggle-summary"
              onClick={() => setShowControls((s) => !s)}
            >
              {showControls ? "Hide search settings ▲" : "Search settings ▼"}
            </button>
          </div>
          {showControls && <ControlsPanel settings={settings} onChange={setSettings} />}
        </form>

        {loading && (
          <div className="status-strip">
            <span className="spinner" />
            Running ARM A / B / C / PV / D and cross-encoder reranking…
          </div>
        )}

        {error && <div className="error-banner">⚠️ {error}</div>}

        {data && (
          <>
            {settings.show_debug && <PipelineDebugPanel data={data} />}

            <ArmDCard armD={data.arm_d} />

            <div className="tabs-row">
              <button
                className={`tab-btn ${activeTab === "academic" ? "active" : ""}`}
                onClick={() => setActiveTab("academic")}
                type="button"
              >
                📚 Academic Prior Art
                <span className="tab-count">{data.academic.results.length}</span>
              </button>
              <button
                className={`tab-btn ${activeTab === "patent" ? "active" : ""}`}
                onClick={() => setActiveTab("patent")}
                type="button"
              >
                🗂️ Patent Prior Art
                <span className="tab-count">{data.patent.results.length}</span>
              </button>
            </div>

            {activeTab === "academic" && (
              <AcademicTab data={data} settings={settings} />
            )}
            {activeTab === "patent" && (
              <PatentTab data={data} settings={settings} />
            )}

            <GlobalReportSection
              globalReport={data.global_report}
              enabled={settings.enable_global_report}
            />
          </>
        )}
      </main>

      <Footer />
    </div>
  );
}

function AcademicTab({ data, settings }) {
  const { academic } = data;
  if (!academic.pipeline_ran) {
    return <div className="empty-state"><p>No academic candidates were retrieved. See warnings above.</p></div>;
  }
  if (academic.results.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">✅</div>
        <h3>No conflicting academic prior art found above {academic.effective_threshold}% fused threshold</h3>
        <p>All retrieval arms + cross-encoder agree: your idea shows strong novelty potential.</p>
      </div>
    );
  }
  return (
    <>
      <div className="results-header">
        {academic.results.length} result{academic.results.length !== 1 ? "s" : ""} above{" "}
        {academic.effective_threshold}% — reranked by fused score
      </div>
      {academic.results.map((r) => (
        <AcademicResultCard
          key={r.rank}
          result={r}
          showDebug={settings.show_debug}
          highlightThresholdPct={settings.highlight_threshold_pct}
        />
      ))}
    </>
  );
}

function PatentTab({ data, settings }) {
  const { patent } = data;

  if (!patent.enabled) {
    return (
      <div className="empty-state">
        <p>Patent search (ARM PV) is disabled. Enable it in search settings to query PatentsView.</p>
      </div>
    );
  }

  return (
    <>
      {settings.show_debug && <PatentDiagnosticsPanel patent={patent} />}

      {patent.error && patent.after_dedup_count === 0 && (
        <div className="warning-banner">⚠️ PatentsView query error: {patent.error}</div>
      )}

      {patent.results.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">✅</div>
          <h3>No relevant patents found above threshold</h3>
          <p>
            PatentsView returned no matching USPTO patents for the extracted keyphrases. Try broadening your
            description or lowering the display threshold.
          </p>
        </div>
      ) : (
        <>
          <div className="results-header">
            <span className="arm-badge arm-pv">ARM PV</span> {patent.results.length} patent candidate
            {patent.results.length !== 1 ? "s" : ""} · YAKE keyphrases:{" "}
            {patent.keyphrases_used.slice(0, 6).join(", ")} · source: PatentsView (USPTO)
          </div>
          {patent.results.map((p) => (
            <PatentResultCard
              key={p.rank}
              result={p}
              showDebug={settings.show_debug}
              highlightThresholdPct={settings.highlight_threshold_pct}
            />
          ))}
        </>
      )}
    </>
  );
}

function Masthead({ elapsed }) {
  return (
    <header className="masthead">
      <div className="masthead-rule-top" />
      <div className="masthead-inner">
        <div className="masthead-title-block">
          <div>
            <h1 className="masthead-title">Docket</h1>
            <div className="masthead-subtitle">PRIOR ART VALIDATION ENGINE</div>
          </div>
          <span className="masthead-mark">v11 · LLM-Guided Hybrid</span>
        </div>
        <div className="masthead-meta">
          ARM A·B·C·PV·D + GLOBAL REPORT
          <br />
          {elapsed != null ? `LAST RUN ${elapsed}s` : "AWAITING FILING"}
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        Powered by <strong>YAKE</strong> · <strong>OpenAlex Concept Graph</strong> ·{" "}
        <strong>BAAI/bge-small-en-v1.5</strong> · <strong>Cross-Encoder MS-MARCO</strong> ·{" "}
        <strong>ARM-C Keyword Fallback</strong> · <strong>ARM-PV PatentsView USPTO</strong> ·{" "}
        <strong>ARM-D Gemini Problem/Method Alignment</strong>
        <br />
        Global Patentability &amp; Novelty Report is Gemini-assisted and is not legal advice.
      </div>
    </footer>
  );
}
