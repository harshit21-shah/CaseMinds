import { Brain, BookOpen, GitBranch, ShieldCheck, Check, Loader2, Circle } from "lucide-react";
import type { AgentStep } from "../types/api";

const ICONS: Record<string, typeof Brain> = {
  QueryClassifier: Brain,
  RetrievalAgent: BookOpen,
  GraphTraversal: GitBranch,
  VerificationAnswer: ShieldCheck,
};

interface AgentPipelineProps {
  steps: AgentStep[];
  visible: boolean;
}

export function AgentPipeline({ steps, visible }: AgentPipelineProps) {
  if (!visible) return null;

  return (
    <div className="animate-slide-up glass-card p-6">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
        Agent Pipeline
      </h3>
      <div className="space-y-3">
        {steps.map((step, i) => {
          const Icon = ICONS[step.id] ?? Circle;
          return (
            <div
              key={step.id}
              className={`flex items-start gap-4 rounded-xl p-3 transition-all ${
                step.status === "active"
                  ? "bg-gold-500/10 border border-gold-500/20"
                  : step.status === "done"
                    ? "bg-emerald-500/5 border border-emerald-500/10"
                    : "border border-transparent opacity-50"
              }`}
            >
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                  step.status === "active"
                    ? "bg-gold-500/20 text-gold-400"
                    : step.status === "done"
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "bg-slate-800 text-slate-600"
                }`}
              >
                {step.status === "active" ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : step.status === "done" ? (
                  <Check className="h-5 w-5" />
                ) : (
                  <Icon className="h-5 w-5" />
                )}
              </div>
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{step.label}</span>
                  <span className="text-xs text-slate-600">Step {i + 1}/4</span>
                </div>
                <p className="mt-0.5 text-sm text-slate-500">{step.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export const INITIAL_STEPS: AgentStep[] = [
  {
    id: "QueryClassifier",
    label: "Query Classifier",
    description: "Classifying query type & routing strategy",
    status: "pending",
  },
  {
    id: "RetrievalAgent",
    label: "Retrieval Agent",
    description: "BM25 + dense hybrid search + CrossEncoder rerank",
    status: "pending",
  },
  {
    id: "GraphTraversal",
    label: "Graph Traversal",
    description: "Expanding via citation graph (2-hop BFS)",
    status: "pending",
  },
  {
    id: "VerificationAnswer",
    label: "Verification + Answer",
    description: "Generating & verifying every citation",
    status: "pending",
  },
];
