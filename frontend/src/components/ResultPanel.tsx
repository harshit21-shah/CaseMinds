import { AlertCircle, BookMarked, Clock, Tag } from "lucide-react";
import type { QueryResponse } from "../types/api";
import { CitationCard } from "./CitationCard";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { FeedbackBar } from "./FeedbackBar";
import { OverruledBanner } from "./OverruledBanner";

interface ResultPanelProps {
  result: QueryResponse;
}

function StatusBadge({ status }: { status: string }) {
  const styles =
    status === "COMPLETE"
      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
      : status === "NO_RESULTS"
        ? "bg-red-500/20 text-red-400 border-red-500/30"
        : "bg-amber-500/20 text-amber-400 border-amber-500/30";

  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${styles}`}>
      {status.replace("_", " ")}
    </span>
  );
}

function cleanAnswer(text: string): string {
  return text
    .replace(/\n---\n\*CaseMinds is a research aid.*$/s, "")
    .replace(/\*CaseMinds is a research aid.*$/s, "")
    .trim();
}

export function ResultPanel({ result }: ResultPanelProps) {
  const answer = cleanAnswer(result.answer);
  const isAbstention =
    answer.toLowerCase().includes("could not find sufficient authority") ||
    result.status === "NO_RESULTS";
  const hasCitations = result.citations.length > 0;

  return (
    <div className="animate-slide-up space-y-6">
      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={result.status} />
        {result.query_type && (
          <span className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-400">
            <Tag className="h-3 w-3" />
            {result.query_type}
          </span>
        )}
        <span className="flex items-center gap-1.5 text-xs text-slate-500">
          <Clock className="h-3 w-3" />
          {(result.latency_ms / 1000).toFixed(1)}s
        </span>
      </div>

      <ConfidenceMeter confidence={result.confidence} status={result.status} />

      {/* Overruled warnings */}
      <OverruledBanner warnings={result.overruled_warnings} />

      {/* Low confidence notice — but still show answer if present */}
      {result.status === "LOW_CONFIDENCE" && !isAbstention && (
        <div className="flex gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-200/90">
          <AlertCircle className="h-5 w-5 shrink-0 text-amber-400" />
          <p>
            Some citations could not be fully verified. Review the sources below and verify
            independently before relying on this answer.
          </p>
        </div>
      )}

      {/* Full abstention */}
      {isAbstention && (
        <div className="glass-card border-slate-700/50 p-6 text-center">
          <AlertCircle className="mx-auto h-10 w-10 text-slate-500" />
          <p className="mt-3 text-slate-400">{answer}</p>
          <p className="mt-2 text-sm text-slate-600">
            Try rephrasing, or search{" "}
            <a
              href="https://indiankanoon.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-gold-400 hover:underline"
            >
              Indian Kanoon
            </a>{" "}
            directly.
          </p>
        </div>
      )}

      {/* Answer */}
      {!isAbstention && answer && (
        <section>
          <h3 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-white">
            <BookMarked className="h-5 w-5 text-gold-400" />
            Answer
          </h3>
          <div className="glass-card border-white/10 p-6">
            <p className="whitespace-pre-wrap text-base leading-relaxed text-slate-300">{answer}</p>
          </div>
        </section>
      )}

      {/* Citations */}
      {hasCitations && (
        <section>
          <h3 className="mb-4 font-display text-lg font-semibold text-white">
            Verified Citations ({result.citations.length})
          </h3>
          <div className="space-y-3">
            {result.citations.map((c) => (
              <CitationCard key={c.doc_id} citation={c} />
            ))}
          </div>
        </section>
      )}

      {/* Footer */}
      <div className="border-t border-white/5 pt-6 space-y-4">
        <FeedbackBar traceId={result.trace_id} />
        <p className="text-xs text-slate-600">
          {result.disclaimer} · Trace: <code className="text-slate-500">{result.trace_id.slice(0, 8)}…</code>
        </p>
      </div>
    </div>
  );
}
