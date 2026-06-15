import { AlertTriangle } from "lucide-react";
import type { OverruledWarning } from "../types/api";

export function OverruledBanner({ warnings }: { warnings: OverruledWarning[] }) {
  if (warnings.length === 0) return null;

  return (
    <div className="space-y-3">
      {warnings.map((w) => (
        <div
          key={w.doc_id}
          className="flex gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4"
        >
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
          <div>
            <p className="font-medium text-amber-200">Overruled case on retrieval path</p>
            <p className="mt-1 text-sm text-amber-200/80">
              <em>{w.case_name}</em>
              {w.overruled_by && (
                <> — overruled by doc <code className="text-xs">{w.overruled_by}</code></>
              )}
            </p>
            <p className="mt-1 text-xs text-amber-400/70">Do not rely on this as current good law.</p>
          </div>
        </div>
      ))}
    </div>
  );
}
