import { bucketForScore, type MatchBucket } from "@/lib/jobs/buckets";

const bucketStyles: Record<MatchBucket, string> = {
  best: "bg-[#1f6b59] text-white",
  strong: "bg-[#e5f0ec] text-[#1f6b59]",
  potential: "bg-[#fff0eb] text-[#a33c1d]",
  low: "bg-[#e8e6df] text-[#6d787e]",
};

export function ScoreBadge({ score }: { score: number }) {
  const bucket = bucketForScore(score);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${bucketStyles[bucket]}`}
    >
      <span className="tabular-nums">{score}</span>
      <span className="opacity-70">{bucket}</span>
    </span>
  );
}