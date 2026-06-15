import { ExternalLink, AlertTriangle } from "lucide-react";
import type { Citation } from "../types/api";

interface CitationCardProps {
  citation: Citation;
}

export function CitationCard({ citation }: CitationCardProps) {
  const overruled = citation.is_overruled;

  return (
    <article
      className={`group rounded-xl border p-5 transition-all hover:shadow-lg ${
        overruled
          ? "border-amber-500/30 bg-amber-500/5 hover:border-amber-500/50"
          : "border-white/10 bg-white/[0.03] hover:border-gold-500/20 hover:bg-white/[0.05]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-medium text-white">{citation.case_name}</h4>
            {overruled && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-400">
                <AlertTriangle className="h-3 w-3" />
                Overruled
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-500">
            {citation.citation && <span>{citation.citation}</span>}
            {citation.court && <span>{citation.court}</span>}
            {citation.date && <span>{citation.date}</span>}
          </div>
        </div>
        {citation.kanoon_url && (
          <a
            href={citation.kanoon_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost shrink-0 text-gold-400 hover:text-gold-300"
          >
            <ExternalLink className="h-4 w-4" />
            Kanoon
          </a>
        )}
      </div>
      {citation.excerpt && (
        <blockquote className="mt-3 border-l-2 border-gold-500/30 pl-4 text-sm italic text-slate-400">
          &ldquo;{citation.excerpt.slice(0, 280)}
          {citation.excerpt.length > 280 ? "…" : ""}&rdquo;
        </blockquote>
      )}
    </article>
  );
}
