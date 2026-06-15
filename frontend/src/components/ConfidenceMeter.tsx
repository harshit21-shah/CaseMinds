interface ConfidenceMeterProps {
  confidence: number;
  status: string;
}

export function ConfidenceMeter({ confidence, status }: ConfidenceMeterProps) {
  const pct = Math.round(confidence * 100);
  const isComplete = status === "COMPLETE";
  const isLow = confidence < 0.6;

  const barColor = isComplete
    ? "from-emerald-500 to-emerald-400"
    : isLow
      ? "from-slate-500 to-slate-400"
      : "from-amber-500 to-gold-400";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400">Citation verification confidence</span>
        <span
          className={`font-semibold ${
            isComplete ? "text-emerald-400" : isLow ? "text-slate-400" : "text-amber-400"
          }`}
        >
          {pct}%
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full bg-gradient-to-r transition-all duration-700 ${barColor}`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
    </div>
  );
}
