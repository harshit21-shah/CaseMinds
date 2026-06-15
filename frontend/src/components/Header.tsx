import { Scale, Sparkles } from "lucide-react";

export function Header() {
  return (
    <header className="flex items-center justify-between border-b border-white/5 px-6 py-4 lg:px-10">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-gold-500 to-gold-600 shadow-lg shadow-gold-500/20">
          <Scale className="h-6 w-6 text-navy-950" strokeWidth={2.2} />
        </div>
        <div>
          <h1 className="font-display text-xl font-bold tracking-tight text-white lg:text-2xl">
            CaseMinds
          </h1>
          <p className="text-xs text-slate-500 lg:text-sm">
            GraphRAG legal research · verified citations
          </p>
        </div>
      </div>
      <div className="hidden items-center gap-2 rounded-full border border-gold-500/20 bg-gold-500/5 px-4 py-1.5 text-xs text-gold-400 sm:flex">
        <Sparkles className="h-3.5 w-3.5" />
        Indian Supreme Court &amp; High Court corpus
      </div>
    </header>
  );
}
