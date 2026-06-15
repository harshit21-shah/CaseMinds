import { useCallback, useEffect, useState } from "react";
import type { AgentStep, QueryResponse } from "./types/api";
import { fetchHealth, streamQuery } from "./lib/api";
import { AgentPipeline, INITIAL_STEPS } from "./components/AgentPipeline";
import { Header } from "./components/Header";
import { ResultPanel } from "./components/ResultPanel";
import { SearchBar } from "./components/SearchBar";
import { Sidebar } from "./components/Sidebar";

const AGENT_ORDER = [
  "QueryClassifier",
  "RetrievalAgent",
  "GraphTraversal",
  "VerificationAnswer",
] as const;

function advanceSteps(completedAgent: string): AgentStep[] {
  const idx = AGENT_ORDER.indexOf(completedAgent as (typeof AGENT_ORDER)[number]);
  return INITIAL_STEPS.map((step, i) => {
    if (idx >= 0 && i <= idx) return { ...step, status: "done" as const };
    if (idx >= 0 && i === idx + 1) return { ...step, status: "active" as const };
    return step;
  });
}

export default function App() {
  const [health, setHealth] = useState<Awaited<ReturnType<typeof fetchHealth>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>(INITIAL_STEPS);
  const [showPipeline, setShowPipeline] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [currentQuery, setCurrentQuery] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
    const interval = setInterval(() => {
      fetchHealth().then(setHealth).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  const runQuery = useCallback((query: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setCurrentQuery(query);
    setShowPipeline(true);
    setSteps(INITIAL_STEPS.map((s, i) => ({ ...s, status: i === 0 ? "active" : "pending" })));

    if (!history.includes(query)) {
      setHistory((h) => [query, ...h].slice(0, 5));
    }

    const cancel = streamQuery(
      query,
      (event) => {
        const ev = event.event as string;

        if (ev === "agent_start") {
          const agent = event.agent as string;
          const idx = AGENT_ORDER.indexOf(agent as (typeof AGENT_ORDER)[number]);
          setSteps(
            INITIAL_STEPS.map((s, i) => ({
              ...s,
              status: i < idx ? "done" : i === idx ? "active" : "pending",
            })),
          );
        }

        if (ev === "agent_complete" && event.agent) {
          setSteps(advanceSteps(event.agent as string));
        }

        if (ev === "answer" && event.data) {
          setSteps(INITIAL_STEPS.map((s) => ({ ...s, status: "done" as const })));
          setResult(event.data as QueryResponse);
          setLoading(false);
        }

        if (ev === "error") {
          setError((event.detail as string) ?? "Pipeline error");
          setLoading(false);
        }
      },
      (err) => {
        setError(err.message);
        setLoading(false);
      },
    );

    return cancel;
  }, [history]);

  const handleSearch = (query: string) => {
    setCurrentQuery(query);
    runQuery(query);
  };

  const handleSelectQuery = (query: string) => {
    setCurrentQuery(query);
    runQuery(query);
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <div className="flex flex-1 flex-col lg:flex-row">
        <Sidebar
          health={health}
          history={history}
          onSelectQuery={handleSelectQuery}
          onSelectExample={handleSelectQuery}
        />

        <main className="flex flex-1 flex-col px-6 py-8 lg:px-12">
          {/* Hero / search */}
          <div className={`flex flex-col items-center ${result || showPipeline ? "mb-8" : "flex-1 justify-center"}`}>
            {!result && !showPipeline && (
              <div className="mb-10 max-w-2xl text-center">
                <h2 className="font-display text-3xl font-bold text-white lg:text-4xl">
                  Research Indian law with{" "}
                  <span className="bg-gradient-to-r from-gold-400 to-gold-600 bg-clip-text text-transparent">
                    verified citations
                  </span>
                </h2>
                <p className="mt-4 text-slate-500">
                  GraphRAG-powered assistant for Supreme Court &amp; High Court judgments.
                  Every citation checked against our corpus — no fabricated cases.
                </p>
              </div>
            )}

            <SearchBar
              onSearch={handleSearch}
              loading={loading}
              value={currentQuery}
              onChange={setCurrentQuery}
            />
          </div>

          {/* Error */}
          {error && (
            <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
              {error}
              <p className="mt-1 text-red-400/70">
                Make sure the API is running on port 8080:{" "}
                <code className="text-xs">python -m uvicorn services.api.main:app --port 8080</code>
              </p>
            </div>
          )}

          {/* Pipeline progress */}
          <div className="mx-auto w-full max-w-3xl space-y-8">
            <AgentPipeline steps={steps} visible={showPipeline && loading} />

            {/* Results */}
            {result && !loading && <ResultPanel result={result} />}
          </div>
        </main>
      </div>
    </div>
  );
}
