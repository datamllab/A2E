import { useCallback, useEffect, useState } from "react";
import { listExperiments } from "./api/experiments";
import type { ExperimentSummary } from "./api/types";
import { Deck } from "./components/Deck";

export default function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const exps = await listExperiments();
      setExperiments(exps);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="overlay">
        <div className="overlay-card">
          <div className="spinner" />
          <p className="overlay-msg">Loading benchmarks…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="overlay">
        <div className="overlay-card">
          <p className="overlay-msg">{error}</p>
          <button type="button" className="retry" onClick={load}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return <Deck experiments={experiments} />;
}
