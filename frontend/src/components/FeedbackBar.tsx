import { ThumbsUp, ThumbsDown, Minus, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { submitFeedback } from "../lib/api";

interface FeedbackBarProps {
  traceId: string;
}

export function FeedbackBar({ traceId }: FeedbackBarProps) {
  const [sent, setSent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const send = async (rating: "HELPFUL" | "NOT_HELPFUL" | "PARTIALLY_HELPFUL") => {
    if (loading || sent) return;
    setLoading(true);
    try {
      await submitFeedback(traceId, rating);
      setSent(rating);
    } catch {
      setSent("error");
    } finally {
      setLoading(false);
    }
  };

  if (sent && sent !== "error") {
    return (
      <div className="flex items-center gap-2 text-sm text-emerald-400">
        <CheckCircle2 className="h-4 w-4" />
        Thanks for your feedback!
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-sm text-slate-500">Was this helpful?</span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => send("HELPFUL")}
          disabled={loading}
          className="btn-ghost border border-white/5 hover:border-emerald-500/30 hover:text-emerald-400"
        >
          <ThumbsUp className="h-4 w-4" />
          Yes
        </button>
        <button
          type="button"
          onClick={() => send("PARTIALLY_HELPFUL")}
          disabled={loading}
          className="btn-ghost border border-white/5"
        >
          <Minus className="h-4 w-4" />
          Partial
        </button>
        <button
          type="button"
          onClick={() => send("NOT_HELPFUL")}
          disabled={loading}
          className="btn-ghost border border-white/5 hover:border-red-500/30 hover:text-red-400"
        >
          <ThumbsDown className="h-4 w-4" />
          No
        </button>
      </div>
    </div>
  );
}
