import { Database, GitBranch, BookOpen, Clock, History, Zap } from "lucide-react";
import type { HealthResponse } from "../types/api";

const EXAMPLES = [
  "What is Section 138 NI Act cheque dishonour?",
  "What is Section 370 IPC?",
  "Conditions for anticipatory bail under Section 438 CrPC",
  "Order 39 CPC temporary injunction requirements",
  "Section 498A IPC dowry cruelty elements",
];

interface SidebarProps {
  health: HealthResponse | null;
  history: string[];
  onSelectQuery: (q: string) => void;
  onSelectExample: (q: string) => void;
}

export function Sidebar({ health, history, onSelectQuery, onSelectExample }: SidebarProps) {
  return (
    <aside className="flex w-full flex-col gap-6 border-b border-white/5 p-6 lg:w-72 lg:shrink-0 lg:border-b-0 lg:border-r">
      {/* System health */}
      <section>
        <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <Zap className="h-3.5 w-3.5" />
          System Status
        </h2>
        {health ? (
          <div className="glass-card space-y-3 p-4">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse-soft" />
              <span className="text-sm font-medium text-emerald-400">Online</span>
            </div>
            {health.corpus_size < 1 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200/90">
                Corpus empty — seed via admin API (see DEPLOYMENT.md). No Render Shell needed.
              </div>
            )}
            <div className="grid grid-cols-1 gap-2 text-sm">
              <Stat icon={BookOpen} label="Judgments" value={health.corpus_size} />
              <Stat icon={GitBranch} label="Graph nodes" value={health.graph_nodes} />
              <Stat icon={Database} label="Citations" value={health.graph_edges} />
            </div>
          </div>
        ) : (
          <div className="glass-card p-4 text-sm text-slate-500">Connecting to API…</div>
        )}
      </section>

      {/* Example queries */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Try these
        </h2>
        <div className="space-y-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onSelectExample(q)}
              className="w-full rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5 text-left text-sm text-slate-400 transition-all hover:border-gold-500/20 hover:bg-gold-500/5 hover:text-slate-200"
            >
              {q}
            </button>
          ))}
        </div>
      </section>

      {/* History */}
      {history.length > 0 && (
        <section>
          <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <History className="h-3.5 w-3.5" />
            Recent
          </h2>
          <div className="space-y-1">
            {history.map((q, i) => (
              <button
                key={`${q}-${i}`}
                type="button"
                onClick={() => onSelectQuery(q)}
                className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm text-slate-500 hover:bg-white/5 hover:text-slate-300"
              >
                <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span className="line-clamp-2">{q}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </aside>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof BookOpen;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-slate-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      <span className="font-mono text-slate-300">{value.toLocaleString()}</span>
    </div>
  );
}
