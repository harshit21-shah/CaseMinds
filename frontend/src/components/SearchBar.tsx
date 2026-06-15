import { Search, Loader2 } from "lucide-react";
import { FormEvent } from "react";

interface SearchBarProps {
  onSearch: (query: string) => void;
  loading: boolean;
  value: string;
  onChange: (query: string) => void;
}

export function SearchBar({ onSearch, loading, value, onChange }: SearchBarProps) {
  const query = value;
  const setQuery = onChange;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim() && !loading) onSearch(query.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-3xl">
      <div className="group relative">
        <div className="absolute -inset-0.5 rounded-2xl bg-gradient-to-r from-gold-500/40 via-gold-400/20 to-transparent opacity-0 blur transition-opacity group-focus-within:opacity-100" />
        <div className="relative flex items-center gap-2 rounded-2xl border border-white/10 bg-navy-900/80 p-2 pl-5 shadow-2xl backdrop-blur-sm transition-colors focus-within:border-gold-500/30">
          <Search className="h-5 w-5 shrink-0 text-slate-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about Indian law — e.g. What is Section 138 NI Act?"
            className="min-w-0 flex-1 bg-transparent py-3 text-base text-white placeholder:text-slate-500 focus:outline-none"
            disabled={loading}
            maxLength={1000}
          />
          <button type="submit" disabled={loading || !query.trim()} className="btn-primary shrink-0 px-5 py-2.5">
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Researching
              </>
            ) : (
              "Search"
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
