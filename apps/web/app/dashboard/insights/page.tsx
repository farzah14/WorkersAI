import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function InsightsPage() {
  const t = await getTranslations();

  const dimensions = [
    { name: t("dimensions.skills"), weight: "35%", desc: t("insights.skillsDesc") },
    { name: t("dimensions.experience"), weight: "25%", desc: t("insights.experienceDesc") },
    { name: t("dimensions.seniority"), weight: "15%", desc: t("insights.seniorityDesc") },
    { name: t("dimensions.education"), weight: "10%", desc: t("insights.educationDesc") },
    { name: t("dimensions.language"), weight: "8%", desc: t("insights.languageDesc") },
    { name: t("dimensions.location"), weight: "7%", desc: t("insights.locationDesc") },
  ];

  const buckets = [
    { name: t("buckets.best"), range: "90% - 100%", color: "bg-[#1f6b59] text-white", desc: t("insights.bestDesc") },
    { name: t("buckets.strong"), range: "71% - 89%", color: "bg-[#d9623c] text-white", desc: t("insights.strongDesc") },
    { name: t("buckets.potential"), range: "50% - 70%", color: "bg-[#e5a93c] text-white", desc: t("insights.potentialDesc") },
    { name: t("buckets.low"), range: "< 50%", color: "bg-[#6d787e] text-white", desc: t("insights.lowDesc") },
  ];

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
            {t("insights.tag")}
          </p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">
            {t("insights.title")}
          </h1>
          <p className="mt-2 text-[#53616a]">
            {t("insights.subheading")}
          </p>
        </header>

        {/* Scoring Weights Grid */}
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">{t("insights.scoringTitle")}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dimensions.map((dim) => (
              <div
                key={dim.name}
                className="rounded-2xl border border-[#d9d5cc] bg-white p-5 shadow-[0_12px_40px_rgba(21,33,43,0.05)]"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#15212b]">{dim.name}</span>
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-md bg-[#fff0eb] text-[#d9623c]">
                    {dim.weight}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-5 text-[#53616a]">{dim.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Match Tiers */}
        <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6 sm:p-8 shadow-[0_12px_40px_rgba(21,33,43,0.05)] space-y-6">
          <h2 className="text-xl font-semibold">{t("insights.bucketsTitle")}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {buckets.map((b) => (
              <div key={b.name} className="p-4 rounded-2xl bg-[#faf9f6] border border-[#d9d5cc] space-y-2">
                <div className="flex items-center justify-between">
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${b.color}`}>
                    {b.name}
                  </span>
                  <span className="font-mono text-xs text-[#6d787e]">{b.range}</span>
                </div>
                <p className="text-xs text-[#53616a]">{b.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Action Prompt */}
        <section className="flex flex-col sm:flex-row items-center justify-between p-6 rounded-3xl bg-[#15212b] text-white">
          <div>
            <h3 className="text-lg font-semibold">{t("insights.actionTitle")}</h3>
            <p className="text-xs text-[#b9c5c9] mt-1">
              {t("insights.actionHint")}
            </p>
          </div>
          <Link
            href="/find-jobs"
            className="mt-4 sm:mt-0 inline-flex rounded-full bg-[#d9623c] px-5 py-2.5 text-xs font-semibold text-white hover:bg-[#bb4f2e] transition"
          >
            {t("insights.actionButton")}
          </Link>
        </section>
      </div>
    </main>
  );
}
