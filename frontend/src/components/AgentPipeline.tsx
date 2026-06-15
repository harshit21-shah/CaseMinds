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
  if (!visible || steps.length === 0) return null;

  return (
    <div className="animate-slide-up glass-card p-6">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
        Agent Pipeline
        <span className="ml-2 normal-case font-normal text-slate-600">— live from backend</span>
      </h3>
      <div className="space-y-3">
        {steps.map((step) => {
          const Icon = ICONS[step.id] ?? Circle;
          const detail =
            step.detail ||
            (step.status === "pending" ? "Waiting…" : step.status === "active" ? "Running…" : "");

          return (
            <div
              key={step.id}
              className={`flex items-start gap-4 rounded-xl p-3 transition-all ${
                step.status === "active"
                  ? "bg-gold-500/10 border border-gold-500/20"
                  : step.status === "done"
                    ? "bg-emerald-500/5 border border-emerald-500/10"
                    : "border border-transparent opacity-40"
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
                  {step.step != null && step.totalSteps != null && (
                    <span className="text-xs text-slate-600">
                      Step {step.step}/{step.totalSteps}
                    </span>
                  )}
                  {step.action && step.status === "done" && (
                    <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-500">
                      {step.action}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 font-mono text-xs leading-relaxed text-slate-400">{detail}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Build empty step placeholders from API meta (labels only). */
export function buildEmptySteps(
  meta: { id: string; label: string }[],
): AgentStep[] {
  return meta.map((m) => ({
    id: m.id as AgentStep["id"],
    label: m.label,
    status: "pending",
    detail: undefined,
    action: undefined,
  }));
}
