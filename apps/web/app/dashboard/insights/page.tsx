import Link from "next/link";

export default async function InsightsPage() {
  const dimensions = [
    { name: "Skills", weight: "35%", desc: "Evaluates exact & semantic matches for mandatory and preferred technical skills." },
    { name: "Experience", weight: "25%", desc: "Compares relevant years of experience against role requirements." },
    { name: "Seniority", weight: "15%", desc: "Measures alignment with track level (Junior, Mid, Senior, Lead)." },
    { name: "Education", weight: "10%", desc: "Checks degree level and field-of-study relevance." },
    { name: "Language", weight: "8%", desc: "Evaluates Indonesian, English, or other language proficiencies." },
    { name: "Location & Mode", weight: "7%", desc: "Scores domestic vs global scope and remote/hybrid compatibility." },
  ];

  const buckets = [
    { name: "Best Match", range: "85% - 100%", color: "bg-[#1f6b59] text-white", desc: "Exceptional alignment with all must-have criteria and strong skill overlap." },
    { name: "Strong Match", range: "70% - 84%", color: "bg-[#d9623c] text-white", desc: "Strong overall profile fit with minor preferred skill or track variations." },
    { name: "Potential", range: "50% - 69%", color: "bg-[#e5a93c] text-white", desc: "Viable role but may contain non-critical gaps or require skill bridging." },
    { name: "Low Match", range: "< 50%", color: "bg-[#6d787e] text-white", desc: "Significant gaps in mandatory requirements or domain alignment." },
  ];

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
            Analytics
          </p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">
            Skills & Match Insights
          </h1>
          <p className="mt-2 text-[#53616a]">
            Understand the explainable logic and weighting behind your job match scores.
          </p>
        </header>

        {/* Scoring Weights Grid */}
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">6-Dimension Scoring Weights</h2>
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
          <h2 className="text-xl font-semibold">Match Buckets</h2>
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
            <h3 className="text-lg font-semibold">Ready to test new preferences?</h3>
            <p className="text-xs text-[#b9c5c9] mt-1">
              Adjust your target roles, locations, or region scope to discover fresh matches.
            </p>
          </div>
          <Link
            href="/find-jobs"
            className="mt-4 sm:mt-0 inline-flex rounded-full bg-[#d9623c] px-5 py-2.5 text-xs font-semibold text-white hover:bg-[#bb4f2e] transition"
          >
            Start Job Search
          </Link>
        </section>
      </div>
    </main>
  );
}
