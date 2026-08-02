import React from "react";

export default function ControlsPanel({ settings, onChange }) {
  const set = (key) => (e) => {
    const val = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    onChange({ ...settings, [key]: val });
  };
  const setNum = (key) => (e) => onChange({ ...settings, [key]: Number(e.target.value) });

  return (
    <div className="controls-panel">
      <div className="control-group">
        <label className="group-label">Display</label>
        <div className="control-row">
          <span>Max results to show</span>
          <span className="range-value">{settings.max_display}</span>
        </div>
        <input
          type="range"
          min={3}
          max={10}
          value={settings.max_display}
          onChange={setNum("max_display")}
          style={{ width: "100%" }}
        />
        <div className="control-row" style={{ marginTop: 10 }}>
          <span>Display threshold</span>
          <span className="range-value">{settings.effective_threshold}%</span>
        </div>
        <input
          type="range"
          min={10}
          max={50}
          value={settings.effective_threshold}
          onChange={setNum("effective_threshold")}
          style={{ width: "100%" }}
        />
      </div>

      <div className="control-group">
        <label className="group-label">Highlighting</label>
        <div className="control-row">
          <span>Sentence highlight threshold</span>
          <span className="range-value">{settings.highlight_threshold_pct}%</span>
        </div>
        <input
          type="range"
          min={60}
          max={95}
          value={settings.highlight_threshold_pct}
          onChange={setNum("highlight_threshold_pct")}
          style={{ width: "100%" }}
        />
        <div className="checkbox-row" style={{ marginTop: 12 }}>
          <input type="checkbox" checked={settings.show_debug} onChange={set("show_debug")} id="show_debug" />
          <label htmlFor="show_debug">Show debug decomposition</label>
        </div>
      </div>

      <div className="control-group">
        <label className="group-label">Retrieval strategy</label>
        <select className="docket-select" value={settings.retrieval_mode} onChange={set("retrieval_mode")}>
          <option>Concept + Full-Text (Recommended)</option>
          <option>Full-Text Only</option>
          <option>Concept-Based Only</option>
        </select>
      </div>

      <div className="control-group">
        <label className="group-label">Arms &amp; reports</label>
        <div className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.enable_patent_search}
            onChange={set("enable_patent_search")}
            id="enable_pv"
          />
          <label htmlFor="enable_pv">🗂️ Patent search (ARM PV)</label>
        </div>
        <div className="checkbox-row">
          <input type="checkbox" checked={settings.enable_arm_d} onChange={set("enable_arm_d")} id="enable_d" />
          <label htmlFor="enable_d">🤖 ARM D (Gemini extraction)</label>
        </div>
        <div className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.enable_global_report}
            onChange={set("enable_global_report")}
            id="enable_report"
          />
          <label htmlFor="enable_report">⚖️ Global Patentability &amp; Novelty Report</label>
        </div>
      </div>
    </div>
  );
}
