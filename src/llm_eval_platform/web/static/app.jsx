const { useEffect, useMemo, useState } = React;

const NAV = ["Board", "Runs", "Compare", "Diagnostics", "Artifacts"];
const METRICS = ["exact_match", "keyword_coverage", "schema_valid", "llm_judge_score"];

function readPath() {
  return window.location.pathname || "/ui";
}

function goto(path) {
  if (window.location.pathname !== path) {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
}

function statusChip(status) {
  if (status === "completed") return "bg-emerald-100 text-emerald-700";
  if (status === "failed") return "bg-rose-100 text-rose-700";
  return "bg-amber-100 text-amber-700";
}

function gateChip(status) {
  return status === "pass"
    ? "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200"
    : "bg-rose-100 text-rose-700 ring-1 ring-rose-200";
}

function fmtPct(value) {
  if (typeof value !== "number") return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function deltaClass(delta, threshold) {
  if (typeof delta !== "number") return "bg-slate-100 text-slate-700";
  if (typeof threshold === "number" && -delta > threshold) return "bg-rose-100 text-rose-700";
  if (delta < 0) return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

function allowedDrop(compareThresholds, metric) {
  return Number(compareThresholds[`max_drop_${metric}`] || 0);
}

async function callApi(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return body;
}

function Field({ label, value, onChange, required = false, placeholder = "" }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-slate-600">{label}</span>
      <input
        className="rounded-lg border border-blue-200 bg-white px-2.5 py-2 text-sm outline-none ring-blue-400 focus:ring-2"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
      />
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-slate-600">{label}</span>
      <select
        className="rounded-lg border border-blue-200 bg-white px-2.5 py-2 text-sm outline-none ring-blue-400 focus:ring-2"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Progress({ value }) {
  const pct = Math.max(0, Math.min(100, (value || 0) * 100));
  return (
    <div className="h-2 rounded bg-slate-100">
      <div className="h-2 rounded bg-blue-500" style={{ width: `${pct}%` }} />
    </div>
  );
}

function JsonView({ title, payload }) {
  return (
    <details className="rounded-lg border border-slate-200 bg-white p-2">
      <summary className="cursor-pointer text-xs font-semibold text-slate-700">{title}</summary>
      <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-xs text-slate-800">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </details>
  );
}

function Sparkline({ values }) {
  if (!values.length) return <p className="text-xs text-slate-500">No trend data yet.</p>;
  const width = 240;
  const height = 56;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = Math.max(0.0001, max - min);
  const points = values
    .map((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * width;
      const y = height - ((v - min) / span) * height;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-14 w-full">
      <polyline fill="none" stroke="#2563eb" strokeWidth="2.5" points={points} />
    </svg>
  );
}

function RunCard({ run, selected, onSelect, pinnedBaselineId, pinnedCandidateId, onPinBaseline, onPinCandidate }) {
  const metrics = run.aggregate_metrics || {};
  const gateStatus = run.gate_decision?.status || "fail";
  return (
    <button
      onClick={() => onSelect(run.run_id)}
      className={
        "w-full rounded-xl border p-3 text-left shadow-sm transition " +
        (selected ? "border-blue-400 bg-blue-50 ring-1 ring-blue-300" : "border-slate-200 bg-white hover:border-blue-200")
      }
    >
      <div className="flex items-center justify-between">
        <p className="font-mono text-xs text-slate-600">{run.run_id}</p>
        <div className="flex items-center gap-2">
          <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + statusChip(run.status)}>{run.status}</span>
          <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + gateChip(gateStatus)}>
            {gateStatus === "pass" ? "Release Safe" : "Release Blocked"}
          </span>
        </div>
      </div>
      <h3 className="mt-2 text-sm font-semibold text-blue-900">{run.variant_name}</h3>
      <p className="text-xs text-slate-600">{run.dataset_name}:{run.dataset_version}</p>
      <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-slate-700">
        <p>Model: {run.model_name}</p>
        <p>Prompt: {run.prompt_version}</p>
        <p>Retrieval: {run.retrieval_enabled ? "On" : "Off"}</p>
        <p>Judge: {run.llm_judge_enabled ? "On" : "Off"}</p>
        <p>Seed: {run.seed}</p>
        <p>Started: {(run.started_at || "").slice(0, 19).replace("T", " ")}</p>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1 text-xs">
        <p className="rounded bg-slate-100 px-2 py-1">EM {fmtPct(metrics.exact_match)}</p>
        <p className="rounded bg-slate-100 px-2 py-1">KW {fmtPct(metrics.keyword_coverage)}</p>
        <p className="rounded bg-slate-100 px-2 py-1">JSON {fmtPct(metrics.schema_valid)}</p>
      </div>
      <div className="mt-2 flex gap-2">
        <span className={"rounded px-2 py-1 text-[10px] font-semibold " + (pinnedBaselineId === run.run_id ? "bg-blue-600 text-white" : "bg-blue-100 text-blue-700")}>
          {pinnedBaselineId === run.run_id ? "Baseline Pinned" : "Baseline"}
        </span>
        <span className={"rounded px-2 py-1 text-[10px] font-semibold " + (pinnedCandidateId === run.run_id ? "bg-indigo-600 text-white" : "bg-indigo-100 text-indigo-700")}>
          {pinnedCandidateId === run.run_id ? "Candidate Pinned" : "Candidate"}
        </span>
      </div>
      <div className="mt-2 flex gap-2 text-[11px]">
        <button type="button" onClick={(e) => { e.stopPropagation(); onPinBaseline(run.run_id); }} className="rounded border border-blue-200 bg-blue-50 px-2 py-1 font-semibold text-blue-700">Pin Baseline</button>
        <button type="button" onClick={(e) => { e.stopPropagation(); onPinCandidate(run.run_id); }} className="rounded border border-indigo-200 bg-indigo-50 px-2 py-1 font-semibold text-indigo-700">Pin Candidate</button>
      </div>
    </button>
  );
}

function RunDetailPage({
  run,
  compare,
  failureAnalysis,
  drift,
  tagMetrics,
  tagMetricsMeta,
  alertTimeline,
  compareThresholds,
  tagPagination,
  onTagPaginationChange,
  onTimelinePaginationChange,
  onBack,
  onComparePinned,
  pinnedBaselineId,
  pinnedCandidateId,
}) {
  const [severityFilter, setSeverityFilter] = useState("all");
  const [metricFilter, setMetricFilter] = useState("");
  if (!run) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-sm text-slate-600">Loading run details...</p>
      </section>
    );
  }
  const filteredTimeline = (alertTimeline?.dataset_alert_timeline || []).filter((a) => {
    if (severityFilter !== "all" && String(a.severity || "").toLowerCase() !== severityFilter) return false;
    if (metricFilter && !String(a.metric || "global").toLowerCase().includes(metricFilter.toLowerCase())) return false;
    return true;
  });
  const degradedSlices = [...(tagMetrics || [])]
    .map((row) => ({
      ...row,
      degradation_score:
        (1 - (row.exact_match || 0)) * 0.4 +
        (1 - (row.keyword_coverage || 0)) * 0.4 +
        (1 - (row.schema_valid || 0)) * 0.2,
    }))
    .sort((a, b) => b.degradation_score - a.degradation_score)
    .slice(0, 5);
  return (
    <div className="grid gap-4">
      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <button onClick={onBack} className="rounded border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
            Back to Board
          </button>
          <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + gateChip(run.release_status === "APPROVED" ? "pass" : "fail")}>
            {run.release_status}
          </span>
        </div>
        <h2 className="mt-3 text-lg font-semibold text-slate-900">{run.variant_name}</h2>
        <p className="font-mono text-xs text-slate-600">{run.run_id}</p>
        <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
          <p>Model: <span className="font-semibold">{run.model_name}</span></p>
          <p>Prompt Version: <span className="font-semibold">{run.prompt_version}</span></p>
          <p>Dataset: <span className="font-semibold">{run.dataset_name}:{run.dataset_version}</span></p>
          <p>Retrieval: <span className="font-semibold">{run.retrieval_enabled ? "On" : "Off"}</span></p>
          <p>Judge: <span className="font-semibold">{run.llm_judge_enabled ? "On" : "Off"}</span></p>
          <p>Seed / Temp: <span className="font-semibold">{run.seed} / {run.temperature}</span></p>
          <p className="md:col-span-3">Signature: <span className="font-mono">{run.experiment_signature}</span></p>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800">Metrics and Gate Context</h3>
          <button
            onClick={onComparePinned}
            className="rounded border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-semibold text-indigo-700"
          >
            Compare pinned ({pinnedBaselineId || "--"} vs {pinnedCandidateId || "--"})
          </button>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {METRICS.map((m) => {
            const v = run.aggregate_metrics && run.aggregate_metrics[m];
            if (v == null) return null;
            return (
              <div key={m} className="rounded border border-slate-100 p-2 text-xs">
                <p className="font-semibold text-slate-700">{m}</p>
                <p className="text-blue-800">{fmtPct(v)}</p>
                <Progress value={v} />
              </div>
            );
          })}
        </div>
        {compare && (
          <div className="mt-3 rounded border border-slate-200 p-2 text-xs">
            <p className="font-semibold text-slate-700">Delta vs Baseline (Allowed Drop Overlay)</p>
            {Object.entries(compare.threshold_overlay || {}).map(([k, row]) => {
              const v = Number(row.delta || 0);
              const allowed = Number(row.allowed_drop || allowedDrop(compareThresholds, k));
              const actualDrop = Number(row.actual_drop || Math.max(0, -v));
              const breach = Number(row.breach || Math.max(0, actualDrop - allowed));
              return (
                <div key={k} className="mt-1 rounded border border-slate-100 p-1.5">
                  <p>
                    {k}: delta {(v * 100).toFixed(2)}% | allowed drop {(allowed * 100).toFixed(2)}% | breach {(breach * 100).toFixed(2)}%
                  </p>
                  <div className="mt-1 grid grid-cols-2 gap-1">
                    <div className="h-2 rounded bg-slate-100">
                      <div className="h-2 rounded bg-blue-500" style={{ width: `${Math.min(100, allowed * 100)}%` }} />
                    </div>
                    <div className="h-2 rounded bg-slate-100">
                      <div className={"h-2 rounded " + (breach > 0 ? "bg-rose-500" : "bg-emerald-500")} style={{ width: `${Math.min(100, actualDrop * 100)}%` }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-800">Failure Preview</h3>
          <div className="mt-2 max-h-72 space-y-2 overflow-auto">
            {failureAnalysis?.worst_samples?.length ? (
              failureAnalysis.worst_samples.slice(0, 10).map((sample) => (
                <div key={sample.item_id} className="rounded border border-rose-200 bg-rose-50 p-2 text-xs">
                  <p className="font-semibold">{sample.item_id} (severity {sample.severity.toFixed(2)})</p>
                  <p><span className="font-semibold">Expected:</span> {sample.expected_answer || "--"}</p>
                  <p><span className="font-semibold">Output:</span> {sample.output_text || "--"}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500">No failures captured.</p>
            )}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-800">Tag Breakdown & Drift</h3>
          <div className="mt-2 max-h-72 space-y-1 overflow-auto text-xs">
            {tagMetrics.length ? (
              tagMetrics.map((row, idx) => (
                <p key={idx}>{row.tag_key}:{row.tag_value} EM {fmtPct(row.exact_match)} KW {fmtPct(row.keyword_coverage)} JSON {fmtPct(row.schema_valid)}</p>
              ))
            ) : (
              <p className="text-slate-500">No tag metrics yet.</p>
            )}
          </div>
          {tagMetrics.length ? (
            <div className="mt-2 flex items-center justify-between text-xs">
              <button
                type="button"
                disabled={tagPagination.offset === 0}
                onClick={() => onTagPaginationChange((p) => ({ ...p, offset: Math.max(0, p.offset - p.limit) }))}
                className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40"
              >
                Prev
              </button>
              <span>{(tagMetricsMeta?.offset || 0) + 1} - {Math.min((tagMetricsMeta?.offset || 0) + (tagMetricsMeta?.limit || 0), (tagMetricsMeta?.total || tagMetrics.length))} / {(tagMetricsMeta?.total || tagMetrics.length)}</span>
              <button
                type="button"
                disabled={!tagMetricsMeta?.has_more}
                onClick={() => onTagPaginationChange((p) => ({ ...p, offset: p.offset + p.limit }))}
                className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          ) : null}
          {drift?.alerts?.length ? (
            <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
              {drift.alerts.map((a, i) => <p key={i}>- {a.message || `${a.metric} ${a.severity}`}</p>)}
            </div>
          ) : null}
          {alertTimeline?.dataset_alert_timeline?.length ? (
            <div className="mt-3 rounded border border-slate-200 p-2 text-xs">
              <p className="font-semibold text-slate-700">Dataset Alert Timeline</p>
              <div className="mt-1 grid grid-cols-2 gap-1">
                <select
                  className="rounded border border-slate-200 px-1 py-1 text-xs"
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                >
                  <option value="all">all severities</option>
                  <option value="critical">critical</option>
                  <option value="warning">warning</option>
                </select>
                <input
                  className="rounded border border-slate-200 px-1 py-1 text-xs"
                  value={metricFilter}
                  onChange={(e) => setMetricFilter(e.target.value)}
                  placeholder="metric filter"
                />
              </div>
              <div className="mt-1 max-h-28 overflow-auto space-y-1">
                {filteredTimeline.slice(0, 20).map((a, idx) => (
                  <p key={idx}>{(a.created_at || "").slice(0, 19).replace("T", " ")} | {a.severity} | {a.metric || "global"} | {a.message}</p>
                ))}
              </div>
              <div className="mt-2 flex items-center justify-between">
                <button
                  type="button"
                  disabled={(alertTimeline.offset || 0) === 0}
                  onClick={() => onTimelinePaginationChange((p) => ({ ...p, offset: Math.max(0, p.offset - p.limit) }))}
                  className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40"
                >
                  Prev
                </button>
                <span>{(alertTimeline.offset || 0) + 1} - {Math.min((alertTimeline.offset || 0) + (alertTimeline.limit || 0), alertTimeline.total || 0)} / {alertTimeline.total || 0}</span>
                <button
                  type="button"
                  disabled={!alertTimeline.has_more}
                  onClick={() => onTimelinePaginationChange((p) => ({ ...p, offset: p.offset + p.limit }))}
                  className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
          {degradedSlices.length ? (
            <div className="mt-3 rounded border border-rose-200 bg-rose-50 p-2 text-xs">
              <p className="font-semibold text-rose-800">Top Degraded Slices</p>
              <div className="mt-1 space-y-1">
                {degradedSlices.map((row, idx) => (
                  <p key={idx}>
                    {row.tag_key}:{row.tag_value} | score {(row.degradation_score * 100).toFixed(1)} | EM {fmtPct(row.exact_match)} KW {fmtPct(row.keyword_coverage)} JSON {fmtPct(row.schema_valid)}
                  </p>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-800">Performance and Observability</h3>
        <div className="mt-2 grid gap-2 text-xs md:grid-cols-4">
          <p>Duration: <span className="font-semibold">{run.duration_ms ? `${run.duration_ms.toFixed(1)} ms` : "--"}</span></p>
          <p>Avg Latency: <span className="font-semibold">{run.avg_latency_ms ? `${run.avg_latency_ms.toFixed(1)} ms` : "--"}</span></p>
          <p>P95 Latency: <span className="font-semibold">{run.p95_latency_ms ? `${run.p95_latency_ms.toFixed(1)} ms` : "--"}</span></p>
          <p>Token Est: <span className="font-semibold">{run.token_in_est || 0} in / {run.token_out_est || 0} out</span></p>
        </div>
      </section>
    </div>
  );
}

function App() {
  const [nav, setNav] = useState("Board");
  const [routePath, setRoutePath] = useState(readPath());
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRun, setSelectedRun] = useState(null);
  const [results, setResults] = useState([]);
  const [compare, setCompare] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [trace, setTrace] = useState([]);
  const [drift, setDrift] = useState(null);
  const [failureAnalysis, setFailureAnalysis] = useState(null);
  const [releaseDecision, setReleaseDecision] = useState(null);
  const [tagMetrics, setTagMetrics] = useState([]);
  const [tagMetricsMeta, setTagMetricsMeta] = useState({ limit: 50, offset: 0, total: 0, has_more: false });
  const [alertTimeline, setAlertTimeline] = useState(null);
  const [localModels, setLocalModels] = useState([]);
  const [pinnedBaselineId, setPinnedBaselineId] = useState("");
  const [pinnedCandidateId, setPinnedCandidateId] = useState("");

  const [registerForm, setRegisterForm] = useState({
    dataset_name: "sample_benchmark",
    version: "v1",
    path: "datasets/sample_benchmark.jsonl",
  });
  const [runForm, setRunForm] = useState({ config_path: "configs/candidate.yaml", model_name: "" });
  const [compareForm, setCompareForm] = useState({
    baseline_run_id: "",
    candidate_run_id: "",
    max_drop_exact_match: "0.05",
    max_drop_keyword_coverage: "0.05",
    max_drop_schema_valid: "0.02",
  });
  const [timelinePagination, setTimelinePagination] = useState({ limit: 20, offset: 0 });
  const [tagPagination, setTagPagination] = useState({ limit: 50, offset: 0 });
  const [exportForm, setExportForm] = useState({ run_id: "", baseline_run_id: "", output_dir: "reports" });

  async function api(path, options = {}) {
    const ts = new Date().toISOString();
    try {
      const payload = await callApi(path, options);
      setTrace((prev) => [{ ts, path, ok: true, payload }, ...prev].slice(0, 30));
      return payload;
    } catch (err) {
      setTrace((prev) => [{ ts, path, ok: false, error: String(err) }, ...prev].slice(0, 30));
      throw err;
    }
  }

  async function refreshRuns() {
    const payload = await api("/runs");
    setRuns(payload.runs || []);
  }

  async function loadRunDetails(runId) {
    if (!runId) return;
    const [runPayload, resultsPayload, driftPayload, failurePayload, releasePayload, tagPayload, alertsPayload] = await Promise.all([
      api(`/runs/${runId}`),
      api(`/runs/${runId}/results`),
      api(`/runs/${runId}/trends`),
      api(`/runs/${runId}/failures?limit=10`),
      api(`/runs/${runId}/release-decision`),
      api(`/runs/${runId}/tag-metrics?limit=${tagPagination.limit}&offset=${tagPagination.offset}`),
      api(`/runs/${runId}/alerts?limit=${timelinePagination.limit}&offset=${timelinePagination.offset}`),
    ]);
    setSelectedRun(runPayload.run);
    setResults(resultsPayload.items || []);
    setDrift(driftPayload.drift);
    setFailureAnalysis(failurePayload);
    setReleaseDecision(releasePayload);
    setTagMetrics(tagPayload.tag_metrics || []);
    setTagMetricsMeta({
      limit: Number(tagPayload.limit ?? tagPagination.limit ?? 50),
      offset: Number(tagPayload.offset ?? tagPagination.offset ?? 0),
      total: Number(tagPayload.total ?? 0),
      has_more: Boolean(tagPayload.has_more),
    });
    setAlertTimeline(alertsPayload);
  }

  useEffect(() => {
    refreshRuns().catch(() => {});
    api("/models/local")
      .then((payload) => setLocalModels(payload.models || []))
      .catch(() => setLocalModels([]));
  }, []);

  useEffect(() => {
    const onPop = () => setRoutePath(readPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    if (selectedRunId) loadRunDetails(selectedRunId).catch(() => {});
  }, [selectedRunId, timelinePagination.limit, timelinePagination.offset, tagPagination.limit, tagPagination.offset]);

  useEffect(() => {
    const match = routePath.match(/^\/ui\/runs\/([^/]+)$/);
    if (match && match[1]) {
      const runId = decodeURIComponent(match[1]);
      setSelectedRunId(runId);
      setNav("Board");
    }
  }, [routePath]);

  useEffect(() => {
    if (runs.length === 0) return;
    if (!selectedRunId) setSelectedRunId(runs[0].run_id);
    if (!pinnedCandidateId) setPinnedCandidateId(runs[0].run_id);
    if (!pinnedBaselineId && runs.length > 1) setPinnedBaselineId(runs[1].run_id);
  }, [runs]);

  useEffect(() => {
    setCompareForm((prev) => ({
      ...prev,
      baseline_run_id: pinnedBaselineId || prev.baseline_run_id,
      candidate_run_id: pinnedCandidateId || prev.candidate_run_id,
    }));
    setExportForm((prev) => ({
      ...prev,
      run_id: pinnedCandidateId || prev.run_id,
      baseline_run_id: pinnedBaselineId || prev.baseline_run_id,
    }));
  }, [pinnedBaselineId, pinnedCandidateId]);

  const groupedRuns = useMemo(() => {
    const groups = {};
    for (const run of runs) {
      const key = `${run.dataset_name}:${run.dataset_version}`;
      groups[key] = groups[key] || [];
      groups[key].push(run);
    }
    return groups;
  }, [runs]);

  const releaseChecklist = useMemo(() => {
    const candidateReady = !!pinnedCandidateId;
    const baselineReady = !!pinnedBaselineId;
    const compared = !!compare;
    const gatePassed = compare?.gate_decision?.status === "pass";
    const exported = !!artifacts;
    const blockers = [];
    if (!candidateReady) blockers.push("Pin a candidate run.");
    if (!baselineReady) blockers.push("Pin a baseline run.");
    if (!compared) blockers.push("Run baseline vs candidate comparison.");
    if (compared && !gatePassed) blockers.push("Regression gate failed.");
    return { candidateReady, baselineReady, compared, gatePassed, exported, blockers };
  }, [pinnedCandidateId, pinnedBaselineId, compare, artifacts]);

  const tagBreakdown = useMemo(() => {
    const acc = {};
    for (const row of results) {
      for (const [tag, value] of Object.entries(row.tags || {})) {
        const key = `${tag}:${value}`;
        if (!acc[key]) acc[key] = { n: 0, exact_match: 0, keyword_coverage: 0, schema_valid: 0 };
        acc[key].n += 1;
        acc[key].exact_match += row.scores.exact_match;
        acc[key].keyword_coverage += row.scores.keyword_coverage;
        acc[key].schema_valid += row.scores.schema_valid;
      }
    }
    return Object.entries(acc).map(([tag, m]) => ({
      tag,
      exact_match: m.exact_match / m.n,
      keyword_coverage: m.keyword_coverage / m.n,
      schema_valid: m.schema_valid / m.n,
    }));
  }, [results]);

  const activeGateStatus = selectedRun?.gate_decision?.status || "fail";
  const activeReleaseStatus = releaseDecision?.release_status || selectedRun?.release_status || "BLOCKED";
  const metricDeltas = compare?.deltas || {};
  const isRunDetailRoute = /^\/ui\/runs\/[^/]+$/.test(routePath);

  const comparePinned = () => {
    if (!pinnedBaselineId || !pinnedCandidateId) return;
    const payload = {
      baseline_run_id: pinnedBaselineId,
      candidate_run_id: pinnedCandidateId,
      gate_config: {
        max_drop_from_baseline: {
          exact_match: Number(compareForm.max_drop_exact_match || 0),
          keyword_coverage: Number(compareForm.max_drop_keyword_coverage || 0),
          schema_valid: Number(compareForm.max_drop_schema_valid || 0),
        },
      },
    };
    setCompareForm((prev) => ({ ...prev, baseline_run_id: pinnedBaselineId, candidate_run_id: pinnedCandidateId }));
    api("/compare", { method: "POST", body: JSON.stringify(payload) }).then((res) => setCompare(res.compare));
  };

  const metricTrends = useMemo(() => {
    if (!selectedRun) return {};
    const sameDatasetRuns = runs
      .filter((r) => r.dataset_name === selectedRun.dataset_name && r.dataset_version === selectedRun.dataset_version)
      .slice()
      .sort((a, b) => (a.started_at || "").localeCompare(b.started_at || ""));
    const out = {};
    for (const metric of ["exact_match", "keyword_coverage", "schema_valid"]) {
      out[metric] = sameDatasetRuns
        .map((r) => r.aggregate_metrics && r.aggregate_metrics[metric])
        .filter((v) => typeof v === "number");
    }
    return out;
  }, [runs, selectedRun]);

  return (
    <main className="mx-auto max-w-[1440px] px-4 py-4 sm:px-6 lg:px-8">
      <header className="rounded-2xl border border-blue-300 bg-gradient-to-r from-blue-900 via-blue-700 to-blue-500 p-5 text-white shadow-md">
        <p className="text-xs font-semibold uppercase tracking-widest text-blue-100">Local-First AI Release Cockpit</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">LLM Evaluation Platform</h1>
        <p className="mt-2 text-sm text-blue-100">
          Dataset → Variant → Run → Metrics → Gates → Compare → Release Decision → Export
        </p>
      </header>

      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        <aside className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm xl:col-span-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-600">Workflow</h2>
          <div className="mt-2 flex flex-col gap-1">
            {NAV.map((item) => (
              <button
                key={item}
                onClick={() => {
                  setNav(item);
                  goto("/ui");
                }}
                className={
                  "rounded-lg px-2 py-2 text-left text-sm font-medium " +
                  (nav === item ? "bg-blue-600 text-white" : "text-slate-700 hover:bg-blue-50")
                }
              >
                {item}
              </button>
            ))}
          </div>
        </aside>

        <section className="flex flex-col gap-4 xl:col-span-7">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">Active Candidate</p>
              <p className="font-mono text-xs text-slate-700">{pinnedCandidateId || selectedRun?.run_id || "--"}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">Release Status</p>
              <p className={"inline-block rounded-full px-2 py-0.5 text-xs font-semibold " + gateChip(activeGateStatus)}>
                {activeReleaseStatus}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">Pinned Baseline</p>
              <p className="font-mono text-xs text-slate-700">{pinnedBaselineId || "--"}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">Baseline Delta Risk</p>
              <p className="text-sm font-medium text-slate-800">
                {Object.keys(metricDeltas).length ? Object.entries(metricDeltas).map(([k, v]) => `${k}:${(v * 100).toFixed(1)}%`).join(" | ") : "--"}
              </p>
            </div>
          </div>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">Run Identity</h3>
            <div className="mt-2 grid gap-2 text-xs md:grid-cols-2">
              <p><span className="font-semibold">Experiment Signature:</span> <span className="font-mono">{selectedRun?.experiment_signature || "--"}</span></p>
              <p><span className="font-semibold">Config Fingerprint:</span> <span className="font-mono">{selectedRun?.config_fingerprint || "--"}</span></p>
              <p><span className="font-semibold">Prompt Fingerprint:</span> <span className="font-mono">{selectedRun?.prompt_fingerprint || "--"}</span></p>
              <p><span className="font-semibold">Dataset Fingerprint:</span> <span className="font-mono">{selectedRun?.dataset_fingerprint || "--"}</span></p>
              <p><span className="font-semibold">Seed:</span> {selectedRun?.seed ?? "--"}</p>
              <p><span className="font-semibold">Temperature:</span> {selectedRun?.temperature ?? "--"}</p>
            </div>
          </section>

          <section className={"rounded-xl border p-4 shadow-sm " + (releaseChecklist.blockers.length ? "border-rose-200 bg-rose-50" : "border-emerald-200 bg-emerald-50")}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-800">Release Decision</h3>
              <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + gateChip(releaseChecklist.gatePassed ? "pass" : "fail")}>
                {releaseChecklist.blockers.length ? "Blocked" : "Ready"}
              </span>
            </div>
            <div className="mt-2 grid gap-1 text-xs text-slate-700 md:grid-cols-2">
              <p>{releaseChecklist.baselineReady ? "✓ Baseline pinned" : "• Baseline not pinned"}</p>
              <p>{releaseChecklist.candidateReady ? "✓ Candidate pinned" : "• Candidate not pinned"}</p>
              <p>{releaseChecklist.compared ? "✓ Drift assessed" : "• Compare not executed"}</p>
              <p>{releaseChecklist.gatePassed ? "✓ Regression gate passed" : "• Gate not passed"}</p>
              <p>{releaseChecklist.exported ? "✓ Artifacts exported" : "• Artifacts pending"}</p>
            </div>
            {releaseChecklist.blockers.length > 0 && (
              <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-rose-700">
                {releaseChecklist.blockers.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            )}
          </section>

          {isRunDetailRoute ? (
            <RunDetailPage
              run={selectedRun}
              compare={compare}
              failureAnalysis={failureAnalysis}
              drift={drift}
              tagMetrics={tagMetrics}
              tagMetricsMeta={tagMetricsMeta}
              alertTimeline={alertTimeline}
              compareThresholds={compareForm}
              tagPagination={tagPagination}
              onTagPaginationChange={setTagPagination}
              onTimelinePaginationChange={setTimelinePagination}
              onBack={() => goto("/ui")}
              onComparePinned={comparePinned}
              pinnedBaselineId={pinnedBaselineId}
              pinnedCandidateId={pinnedCandidateId}
            />
          ) : nav === "Board" && (
            <div className="grid gap-4">
              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-800">Run Timeline by Dataset</h3>
                  <button onClick={() => refreshRuns().catch(() => {})} className="rounded-lg border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
                    Refresh
                  </button>
                </div>
                <div className="grid gap-3">
                  {Object.keys(groupedRuns).length === 0 && <p className="text-sm text-slate-500">No runs found.</p>}
                  {Object.entries(groupedRuns).map(([datasetKey, list]) => (
                    <div key={datasetKey}>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{datasetKey}</p>
                      <div className="grid gap-2 md:grid-cols-2">
                        {list.map((run) => (
                          <RunCard
                            key={run.run_id}
                            run={run}
                            selected={run.run_id === selectedRunId}
                            onSelect={(runId) => {
                              setSelectedRunId(runId);
                              goto(`/ui/runs/${encodeURIComponent(runId)}`);
                            }}
                            pinnedBaselineId={pinnedBaselineId}
                            pinnedCandidateId={pinnedCandidateId}
                            onPinBaseline={setPinnedBaselineId}
                            onPinCandidate={setPinnedCandidateId}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-800">Metric Snapshot</h3>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {METRICS.map((metric) => {
                    const value = selectedRun?.aggregate_metrics?.[metric];
                    if (value == null) return null;
                    return (
                      <div key={metric} className="rounded-lg border border-slate-100 p-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-slate-600">{metric}</span>
                          <span className="font-semibold text-blue-800">{fmtPct(value)}</span>
                        </div>
                        <div className="mt-2">
                          <Progress value={value} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg border border-slate-100 p-2">
                    <p className="text-xs font-medium text-slate-600">Trend: exact_match</p>
                    <Sparkline values={metricTrends.exact_match || []} />
                  </div>
                  <div className="rounded-lg border border-slate-100 p-2">
                    <p className="text-xs font-medium text-slate-600">Trend: keyword_coverage</p>
                    <Sparkline values={metricTrends.keyword_coverage || []} />
                  </div>
                  <div className="rounded-lg border border-slate-100 p-2">
                    <p className="text-xs font-medium text-slate-600">Trend: schema_valid</p>
                    <Sparkline values={metricTrends.schema_valid || []} />
                  </div>
                </div>
                <div className="mt-4 grid gap-2 md:grid-cols-3">
                  <div className="rounded-lg border border-slate-100 p-2 text-xs">
                    <p className="font-semibold text-slate-700">Run Duration</p>
                    <p>{selectedRun?.duration_ms ? `${selectedRun.duration_ms.toFixed(1)} ms` : "--"}</p>
                  </div>
                  <div className="rounded-lg border border-slate-100 p-2 text-xs">
                    <p className="font-semibold text-slate-700">Avg / P95 Latency</p>
                    <p>{selectedRun?.avg_latency_ms ? `${selectedRun.avg_latency_ms.toFixed(1)} / ${selectedRun.p95_latency_ms?.toFixed(1)} ms` : "--"}</p>
                  </div>
                  <div className="rounded-lg border border-slate-100 p-2 text-xs">
                    <p className="font-semibold text-slate-700">Token Estimate / Cost</p>
                    <p>{selectedRun ? `${selectedRun.token_in_est || 0} in, ${selectedRun.token_out_est || 0} out, $${(selectedRun.cost_est_usd || 0).toFixed(2)}` : "--"}</p>
                  </div>
                </div>
              </section>
            </div>
          )}

          {nav === "Runs" && (
            <section className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-800">Dataset Registry</h3>
                <form
                  className="mt-3 grid gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    api("/datasets/register", { method: "POST", body: JSON.stringify(registerForm) })
                      .then(() => refreshRuns())
                      .catch(() => {});
                  }}
                >
                  <Field label="Dataset Name" value={registerForm.dataset_name} onChange={(v) => setRegisterForm({ ...registerForm, dataset_name: v })} required />
                  <Field label="Version" value={registerForm.version} onChange={(v) => setRegisterForm({ ...registerForm, version: v })} required />
                  <Field label="Path" value={registerForm.path} onChange={(v) => setRegisterForm({ ...registerForm, path: v })} required />
                  <button className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                    Add Dataset Version to Registry
                  </button>
                </form>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-800">Execute Candidate Run</h3>
                <form
                  className="mt-3 grid gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const payload = { ...runForm };
                    if (!payload.model_name) delete payload.model_name;
                    api("/runs/from-config", { method: "POST", body: JSON.stringify(payload) })
                      .then((res) => {
                        setSelectedRunId(res.run.run_id);
                        setPinnedCandidateId(res.run.run_id);
                        setExportForm((p) => ({ ...p, run_id: res.run.run_id }));
                        refreshRuns();
                      })
                      .catch(() => {});
                  }}
                >
                  <Field label="Config Path" value={runForm.config_path} onChange={(v) => setRunForm({ config_path: v })} required />
                  <SelectField
                    label="Override Model (Local Ollama)"
                    value={runForm.model_name}
                    onChange={(v) => setRunForm({ ...runForm, model_name: v })}
                    options={[
                      { value: "", label: "Use model from config" },
                      ...localModels.map((m) => ({ value: m, label: m })),
                    ]}
                  />
                  <button className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                    Execute Candidate Run
                  </button>
                </form>
              </div>
            </section>
          )}

          {nav === "Compare" && (
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">Assess Drift vs Baseline</h3>
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                <button
                  type="button"
                  onClick={comparePinned}
                  className="rounded border border-blue-200 bg-blue-50 px-2 py-1 font-semibold text-blue-700"
                >
                  Compare Pinned Runs
                </button>
                <span className="rounded bg-slate-100 px-2 py-1">Baseline: {pinnedBaselineId || "--"}</span>
                <span className="rounded bg-slate-100 px-2 py-1">Candidate: {pinnedCandidateId || "--"}</span>
              </div>
              <form
                className="mt-3 grid gap-2 md:grid-cols-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const payload = {
                    baseline_run_id: compareForm.baseline_run_id,
                    candidate_run_id: compareForm.candidate_run_id,
                    gate_config: {
                      max_drop_from_baseline: {
                        exact_match: Number(compareForm.max_drop_exact_match || 0),
                        keyword_coverage: Number(compareForm.max_drop_keyword_coverage || 0),
                        schema_valid: Number(compareForm.max_drop_schema_valid || 0),
                      },
                    },
                  };
                  api("/compare", { method: "POST", body: JSON.stringify(payload) }).then((res) => setCompare(res.compare));
                }}
              >
                <Field label="Baseline Run ID" value={compareForm.baseline_run_id} onChange={(v) => setCompareForm({ ...compareForm, baseline_run_id: v })} required />
                <Field label="Candidate Run ID" value={compareForm.candidate_run_id} onChange={(v) => setCompareForm({ ...compareForm, candidate_run_id: v })} required />
                <Field label="Max Drop: exact_match" value={compareForm.max_drop_exact_match} onChange={(v) => setCompareForm({ ...compareForm, max_drop_exact_match: v })} />
                <Field label="Max Drop: keyword_coverage" value={compareForm.max_drop_keyword_coverage} onChange={(v) => setCompareForm({ ...compareForm, max_drop_keyword_coverage: v })} />
                <Field label="Max Drop: schema_valid" value={compareForm.max_drop_schema_valid} onChange={(v) => setCompareForm({ ...compareForm, max_drop_schema_valid: v })} />
                <button className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 md:col-span-2">
                  Assess Drift vs Baseline
                </button>
              </form>
              {compare && (
                <div className="mt-4 grid gap-2">
                  <p className={"inline-block w-fit rounded-full px-2 py-0.5 text-xs font-semibold " + gateChip(compare.gate_decision.status)}>
                    {compare.gate_decision.status === "pass" ? "Release Safe" : "Release Blocked"}
                  </p>
                  {Object.entries(compare.threshold_overlay || {}).map(([metric, overlay]) => {
                    const delta = Number(overlay.delta || 0);
                    const allowed = Number(overlay.allowed_drop || allowedDrop(compareForm, metric));
                    const breach = Number(overlay.breach || 0);
                    return (
                    <div key={metric} className="rounded border border-slate-200 px-2 py-1 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-slate-700">{metric}</span>
                        <span className={"rounded px-2 py-0.5 font-semibold " + deltaClass(delta, Number(compareForm[`max_drop_${metric}`]))}>
                          {(delta * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-600">
                        allowed drop {(allowed * 100).toFixed(1)}% | breach {(breach * 100).toFixed(1)}%
                      </p>
                      <div className="mt-1 h-2 rounded bg-slate-100">
                        <div className="h-2 rounded bg-blue-500" style={{ width: `${Math.min(100, allowed * 100)}%` }} />
                      </div>
                    </div>
                    );
                  })}
                </div>
              )}
              {releaseDecision?.drift_alerts?.length > 0 && (
                <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs">
                  <p className="font-semibold text-amber-800">Drift Alerts</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4 text-amber-700">
                    {releaseDecision.drift_alerts.map((alert, idx) => <li key={idx}>{alert.message || `${alert.metric} ${alert.severity}`}</li>)}
                  </ul>
                </div>
              )}
            </section>
          )}

          {nav === "Diagnostics" && (
            <section className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-800">Deterministic Scoring Breakdown</h3>
                <p className="mt-1 text-xs text-slate-600">Per-tag aggregation from run item results.</p>
                <div className="mt-3 grid gap-2">
                  {tagBreakdown.length === 0 && <p className="text-xs text-slate-500">Select a run first.</p>}
                  {tagBreakdown.map((row) => (
                    <div key={row.tag} className="rounded border border-slate-200 p-2">
                      <p className="text-xs font-semibold text-slate-700">{row.tag}</p>
                      <div className="mt-1 grid gap-1 text-xs">
                        <div>EM {fmtPct(row.exact_match)}<Progress value={row.exact_match} /></div>
                        <div>KW {fmtPct(row.keyword_coverage)}<Progress value={row.keyword_coverage} /></div>
                        <div>JSON {fmtPct(row.schema_valid)}<Progress value={row.schema_valid} /></div>
                      </div>
                    </div>
                  ))}
                </div>
                {drift?.volatility && (
                  <div className="mt-3 rounded border border-slate-200 p-2 text-xs">
                    <p className="font-semibold text-slate-700">Volatility</p>
                    {Object.entries(drift.volatility).map(([metric, value]) => (
                      <p key={metric}>{metric}: {(value * 100).toFixed(2)}%</p>
                    ))}
                  </div>
                )}
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-800">Error Diagnostics</h3>
                <div className="mt-3 grid gap-2">
                  {results.filter((r) => r.error).length === 0 && <p className="text-xs text-slate-500">No item-level errors for selected run.</p>}
                  {results.filter((r) => r.error).map((row) => (
                    <div key={row.item_id} className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-800">
                      <p className="font-semibold">item_id: {row.item_id}</p>
                      <p>{row.error}</p>
                    </div>
                  ))}
                </div>
                {failureAnalysis?.worst_samples?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold text-slate-700">Top Failure Samples</p>
                    <div className="mt-1 max-h-56 space-y-1 overflow-auto">
                      {failureAnalysis.worst_samples.slice(0, 5).map((sample) => (
                        <div key={sample.item_id} className="rounded border border-rose-200 bg-rose-50 p-2 text-xs">
                          <p className="font-semibold">{sample.item_id} (severity {sample.severity.toFixed(2)})</p>
                          <p><span className="font-semibold">Expected:</span> {sample.expected_answer || "--"}</p>
                          <p><span className="font-semibold">Output:</span> {sample.output_text || "--"}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {tagMetrics.length > 0 && (
                  <div className="mt-3 rounded border border-slate-200 p-2 text-xs">
                    <p className="font-semibold text-slate-700">Tag Metric Slices</p>
                    <div className="mt-1 max-h-40 overflow-auto">
                      {tagMetrics.map((row, idx) => (
                        <p key={idx}>{row.tag_key}:{row.tag_value} EM {fmtPct(row.exact_match)} KW {fmtPct(row.keyword_coverage)}</p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}

          {nav === "Artifacts" && (
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">Publish Evaluation Artifacts</h3>
              <form
                className="mt-3 grid gap-2 md:grid-cols-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const payload = { ...exportForm };
                  if (!payload.baseline_run_id) delete payload.baseline_run_id;
                  api("/reports/export", { method: "POST", body: JSON.stringify(payload) }).then((res) => setArtifacts(res.artifacts));
                }}
              >
                <Field label="Run ID" value={exportForm.run_id} onChange={(v) => setExportForm({ ...exportForm, run_id: v })} required />
                <Field label="Baseline Run ID (Optional)" value={exportForm.baseline_run_id} onChange={(v) => setExportForm({ ...exportForm, baseline_run_id: v })} />
                <Field label="Output Dir" value={exportForm.output_dir} onChange={(v) => setExportForm({ ...exportForm, output_dir: v })} required />
                <button className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 md:col-span-2">
                  Publish Evaluation Artifacts
                </button>
              </form>
              {artifacts && (
                <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
                  <p className="font-semibold">Portfolio Snapshot Ready</p>
                  <ul className="mt-1 space-y-1 font-mono">
                    <li>{artifacts.markdown_report}</li>
                    <li>{artifacts.json_report}</li>
                    <li>{artifacts.metrics_snapshot}</li>
                  </ul>
                </div>
              )}
            </section>
          )}
        </section>

        <aside className="flex flex-col gap-4 xl:col-span-3">
          <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">Run Execution Trace</h3>
            <div className="mt-2 max-h-64 space-y-2 overflow-auto">
              {trace.length === 0 && <p className="text-xs text-slate-500">No API events yet.</p>}
              {trace.map((entry, i) => (
                <div key={i} className={"rounded border p-2 text-xs " + (entry.ok ? "border-emerald-200 bg-emerald-50" : "border-rose-200 bg-rose-50")}>
                  <p className="font-mono">{entry.ts}</p>
                  <p className="font-semibold">{entry.path}</p>
                  {!entry.ok && <p>{entry.error}</p>}
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">Structured Logs</h3>
            <div className="mt-2 grid gap-2">
              {trace.slice(0, 5).map((entry, idx) => (
                <JsonView key={idx} title={`${entry.path} @ ${entry.ts}`} payload={entry.ok ? entry.payload : { error: entry.error }} />
              ))}
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
