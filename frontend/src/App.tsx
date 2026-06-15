import { useCallback, useEffect, useState } from "react";
import type { AgentStep, QueryResponse } from "./types/api";
import { fetchHealth, fetchPipelineMeta, streamQuery } from "./lib/api";
import { AgentPipeline, buildEmptySteps } from "./components/AgentPipeline";
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

function upsertStep(steps: AgentStep[], update: Partial<AgentStep> & { id: AgentStep["id"] }): AgentStep[] {
  const idx = steps.findIndex((s) => s.id === update.id);
  if (idx === -1) return steps;
  const next = [...steps];
  next[idx] = { ...next[idx], ...update };
  return next;
}

function setActiveAgent(steps: AgentStep[], agentId: AgentStep["id"]): AgentStep[] {
  const activeIdx = AGENT_ORDER.indexOf(agentId);
  return steps.map((s) => {
    const orderIdx = AGENT_ORDER.indexOf(s.id);
    if (orderIdx < activeIdx) return { ...s, status: "done" as const };
    if (orderIdx === activeIdx) return { ...s, status: "active" as const };
    return { ...s, status: "pending" as const };
  });
}

export default function App() {
  const [health, setHealth] = useState<Awaited<ReturnType<typeof fetchHealth>> | null>(null);
  const [agentMeta, setAgentMeta] = useState<{ id: string; label: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [showPipeline, setShowPipeline] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [currentQuery, setCurrentQuery] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
    fetchPipelineMeta()
      .then((m) => setAgentMeta(m.agents))
      .catch(() =>
        setAgentMeta([
          { id: "QueryClassifier", label: "Query Classifier" },
          { id: "RetrievalAgent", label: "Retrieval Agent" },
          { id: "GraphTraversal", label: "Graph Traversal" },
          { id: "VerificationAnswer", label: "Verification + Answer" },
        ]),
      );
    const interval = setInterval(() => {
      fetchHealth().then(setHealth).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  const runQuery = useCallback(
    (query: string) => {
      setLoading(true);
      setError(null);
      setResult(null);
      setCurrentQuery(query);
      setShowPipeline(true);
      setSteps(buildEmptySteps(agentMeta.length ? agentMeta : [
        { id: "QueryClassifier", label: "Query Classifier" },
        { id: "RetrievalAgent", label: "Retrieval Agent" },
        { id: "GraphTraversal", label: "Graph Traversal" },
        { id: "VerificationAnswer", label: "Verification + Answer" },
      ]));

      if (!history.includes(query)) {
        setHistory((h) => [query, ...h].slice(0, 5));
      }

      const cancel = streamQuery(
        query,
        (event) => {
          const ev = event.event as string;
          const agent = event.agent as AgentStep["id"] | undefined;

          if (ev === "agent_start" && agent) {
            setSteps((prev) =>
              upsertStep(setActiveAgent(prev, agent), {
                id: agent,
                label: (event.label as string) || agent,
                step: event.step as number | undefined,
                totalSteps: event.total_steps as number | undefined,
                detail: "Running…",
              }),
            );
          }

          if (ev === "agent_complete" && agent) {
            setSteps((prev) => {
              let next = upsertStep(prev, {
                id: agent,
                status: "done",
                action: event.action as string | undefined,
                detail: (event.detail as string) || "Done",
              });
              const idx = AGENT_ORDER.indexOf(agent);
              const nextAgent = AGENT_ORDER[idx + 1];
              if (nextAgent) {
                next = setActiveAgent(next, nextAgent);
              }
              return next;
            });
          }

          if (ev === "answer" && event.data) {
            setSteps((prev) => prev.map((s) => ({ ...s, status: "done" as const })));
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
    },
    [history, agentMeta],
  );

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
          <div
            className={`flex flex-col items-center ${result || showPipeline ? "mb-8" : "flex-1 justify-center"}`}
          >
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

          {error && (
            <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
              {error}
              <p className="mt-1 text-red-400/70">
                Make sure the API is running on port 8080:{" "}
                <code className="text-xs">make run</code>
              </p>
            </div>
          )}

          <div className="mx-auto w-full max-w-3xl space-y-8">
            <AgentPipeline steps={steps} visible={showPipeline && (loading || steps.some((s) => s.detail))} />

            {result && !loading && <ResultPanel result={result} />}
          </div>
        </main>
      </div>
    </div>
  );
}
