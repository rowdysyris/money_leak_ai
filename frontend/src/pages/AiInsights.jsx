import AppLayout from "../components/AppLayout";
import SectionCard from "../components/SectionCard";
import AppIcon from "../components/ui/AppIcon";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import MetricCard from "../components/ui/MetricCard";
import SkeletonCard from "../components/ui/SkeletonCard";
import useApiResource from "../hooks/useApiResource";
import { formatCurrency, formatNumber, getLeakScoreSeverity, safeArray, toNumber } from "../utils/formatters";

const ICON_MAP = {
  "shopping-bag": "shopping",
  utensils: "utensils",
  repeat: "repeat",
  "calendar-days": "calendar",
  send: "transfer",
  receipt: "receipt",
  zap: "zap",
  scale: "scale",
  wallet: "wallet",
  "question-mark": "help"
};

/**
 * Return a user-facing icon from the backend icon key.
 */
function personalityIcon(iconKey) {
  const key = String(iconKey ?? "").trim();
  if (ICON_MAP[key]) {
    return ICON_MAP[key];
  }
  return "brain";
}

/**
 * Build specific recommendation card text from loaded insight data.
 */
function buildRecommendationCards(priorityRows, scoreData, splitData) {
  const top = priorityRows[0] ?? null;
  const income = toNumber(scoreData?.inputs?.estimated_income ?? scoreData?.details?.income_estimate ?? scoreData?.estimated_income ?? 0);
  const savingsTotal = toNumber(splitData?.savings_total ?? scoreData?.inputs?.savings_total ?? 0);
  const savingsRate = toNumber(splitData?.savings_rate_pct ?? scoreData?.inputs?.savings_rate_pct ?? 0);
  const score = toNumber(scoreData?.score ?? scoreData ?? 0);
  const savingsBasis = income > 0
    ? `Detected monthly income baseline is around ${formatCurrency(income)}. Savings or investment movement in the statement period is ${formatCurrency(savingsTotal)}. Savings rate is capped at ${Math.min(100, savingsRate).toFixed(1)}% when movement exceeds the income baseline.`
    : "Route a fixed amount to investments or savings before discretionary spend begins.";
  return [
    {
      title: top ? `Control ${top.target} first` : "Control the largest leak first",
      body: top ? `${top.reason} Acting on this can save about ${formatCurrency(top.possible_monthly_saving)}/month.` : "Start with the highest-ranked saving action once your statement is analyzed.",
      tone: "bg-blue-50 text-blue-800",
      button: "Review Money Leaks",
      route: "/money-leaks"
    },
    {
      title: "Automate savings",
      body: savingsBasis,
      tone: "bg-green-50 text-green-800",
      button: "Open Budget",
      route: "/budget"
    },
    {
      title: "Review low-confidence merchants",
      body: `Current Money Leak Score is ${formatNumber(score)}. Correcting reviewed merchants improves future category accuracy and recommendations.`,
      tone: "bg-red-50 text-red-800",
      button: "Fix Review Rows",
      route: "/transactions"
    }
  ];
}

/**
 * Explain difficulty labels in plain English.
 */
function difficultyText(difficulty) {
  const value = String(difficulty ?? "medium").toLowerCase();
  if (value === "easy") {
    return "Easy · one-time review";
  }
  if (value === "hard") {
    return "Hard · sustained habit change";
  }
  return "Medium · habit change";
}

/**
 * Return a route for an insight action.
 */
function actionRoute(target) {
  const text = String(target ?? "").toLowerCase();
  if (text.includes("subscription") || text.includes("netflix") || text.includes("spotify") || text.includes("icloud")) {
    return ["/subscriptions", "Open Subscriptions"];
  }
  if (text.includes("duplicate")) {
    return ["/money-leaks", "Review Duplicates"];
  }
  if (text.includes("small") || text.includes("bank")) {
    return ["/money-leaks", "Open Money Leaks"];
  }
  return ["/transactions", "Open Transactions"];
}

/**
 * Render AI and rule-based financial insights.
 */
export default function AiInsights() {
  const personality = useApiResource("/api/insights/spending-personality");
  const priority = useApiResource("/api/insights/saving-priority-list", { initialData: [] });
  const score = useApiResource("/api/insights/money-leak-score");
  const split = useApiResource("/api/dashboard/needs-wants-waste");
  const loading = personality.loading || priority.loading || score.loading || split.loading;
  const error = personality.error || priority.error || score.error || split.error;
  const priorityRows = safeArray(priority.data);
  const noStatement = !loading && personality.data === null && (personality.warnings ?? []).some((warning) => String(warning).includes("No statement"));
  const cards = buildRecommendationCards(priorityRows, score.data, split.data);
  const totalMonthlySavings = priorityRows.reduce((sum, item) => sum + toNumber(item?.possible_monthly_saving), 0);
  const totalYearlySavings = priorityRows.reduce((sum, item) => sum + toNumber(item?.possible_yearly_saving), 0);
  const topAction = priorityRows[0]?.target ?? "—";
  const scoreValue = toNumber(score.data?.score ?? score.data);
  const severity = getLeakScoreSeverity(scoreValue);

  if (loading) {
    return <AppLayout title="AI Insights" subtitle="Spending personality and ranked saving actions."><SkeletonCard height="h-[620px]" /></AppLayout>;
  }

  if (noStatement) {
    return <AppLayout title="AI Insights" subtitle="Spending personality and ranked saving actions."><EmptyState icon="upload" title="Upload your bank statement to get started" description="AI insights need transaction history first." actionLabel="Upload Statement" onAction={() => { window.location.href = "/upload"; }} /></AppLayout>;
  }

  return (
    <AppLayout title="AI Insights" subtitle="Spending personality, ranked actions, and explainable saving priorities.">
      <div className="space-y-6">
        {error ? <ErrorBanner message={error} /> : null}

        <section className="insight-hero border border-slate-800 bg-slate-950 p-6 text-white">
          <p className="text-sm font-black uppercase tracking-[0.25em] text-blue-300">AI financial coach</p>
          <div className="mt-4 grid gap-5 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
            <div>
              <h2 className="text-3xl font-black sm:text-4xl">Start with {topAction}</h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">These are explainable, rule-grounded recommendations. AI wording is layered on top of deterministic analytics, so the advice stays predictable.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-3xl bg-white/10 p-4 ring-1 ring-white/15"><p className="text-xs font-black text-blue-200">Monthly impact</p><p className="mt-1 text-2xl font-black">{formatCurrency(totalMonthlySavings)}</p></div>
              <div className="rounded-3xl bg-white/10 p-4 ring-1 ring-white/15"><p className="text-xs font-black text-blue-200">Leak score</p><p className="mt-1 text-2xl font-black">{formatNumber(scoreValue)} · {severity}</p></div>
            </div>
          </div>
        </section>

        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Monthly Savings Potential" value={formatCurrency(totalMonthlySavings)} subtitle={`Across ${priorityRows.length} detected actions`} icon="check" color="text-green-600" />
          <MetricCard label="Yearly Savings Potential" value={formatCurrency(totalYearlySavings)} subtitle="Projected annual impact" icon="trend-up" color="text-blue-600" />
          <MetricCard label="Top Action" value={topAction} subtitle="Highest expected impact" icon="target" color="text-slate-950" />
          <MetricCard label="Money Leak Score" value={`${formatNumber(scoreValue)} · ${severity}`} subtitle="Lower means healthier control" icon="alert" color={scoreValue > 60 ? "text-red-500" : "text-green-600"} />
        </div>

        <SectionCard title="Spending Personality" subtitle="Based on actionable spend after excluding anomalies and non-spend credits.">
          <div className="rounded-[1.75rem] bg-slate-950 p-5 text-white">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-4">
                <div className="icon-well grid h-16 w-16 place-items-center"><AppIcon name={personalityIcon(personality.data?.icon_suggestion)} size={28} /></div>
                <div>
                  <h2 className="text-3xl font-black">{personality.data?.personality_type ?? "Balanced Spender"}</h2>
                  <p className="mt-2 max-w-2xl text-slate-300">{personality.data?.description ?? "Your spending is spread across categories without a single extreme leakage source."}</p>
                </div>
              </div>
              <div className="grid gap-2 text-sm sm:grid-cols-3 lg:min-w-[420px]">
                <div className="rounded-2xl bg-white/10 p-3"><p className="text-slate-400">Top action</p><p className="font-black">{topAction}</p></div>
                <div className="rounded-2xl bg-white/10 p-3"><p className="text-slate-400">Score</p><p className="font-black">{formatNumber(scoreValue)}</p></div>
                <div className="rounded-2xl bg-white/10 p-3"><p className="text-slate-400">Status</p><p className="font-black">{severity}</p></div>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Saving Priority List" subtitle="Ranked by impact, actionability, and whether the spend is controllable.">
          {priorityRows.length === 0 ? <EmptyState icon="check" title="No saving actions yet" description="Priority actions appear after your statement is analyzed." /> : (
            <div className="grid gap-4 md:grid-cols-2">
              {priorityRows.map((item, index) => {
                const [route, label] = actionRoute(item?.target);
                return (
                  <article key={`${item?.target}-${index}`} className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-black text-blue-600">#{item?.rank ?? index + 1}</p>
                        <h3 className="mt-1 text-xl font-black text-slate-950">{item?.target ?? "Saving opportunity"}</h3>
                      </div>
                      <Badge label={difficultyText(item?.difficulty)} type={item?.difficulty ?? "medium"} />
                    </div>
                    <div className="mt-4 grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
                      <div className="rounded-2xl bg-slate-50 p-4">
                        <p className="text-xs font-black uppercase tracking-wide text-slate-400">Reason</p>
                        <p className="mt-1 text-sm leading-6 text-slate-600">{item?.reason ?? "This recommendation is based on your transaction patterns."}</p>
                        <p className="mt-3 text-xs font-black uppercase tracking-wide text-slate-400">Action</p>
                        <p className="mt-1 text-sm leading-6 text-slate-700">{item?.action ?? "Reduce this category to save more."}</p>
                      </div>
                      <div className="grid gap-3">
                        <div className="rounded-2xl bg-green-50 p-4"><p className="text-xs font-bold text-green-700">Monthly saving</p><p className="text-xl font-black text-green-600">{formatCurrency(item?.possible_monthly_saving)}</p></div>
                        <div className="rounded-2xl bg-blue-50 p-4"><p className="text-xs font-bold text-blue-700">Yearly saving</p><p className="text-xl font-black text-blue-600">{formatCurrency(item?.possible_yearly_saving)}</p></div>
                      </div>
                    </div>
                    <button type="button" onClick={() => { window.location.href = route; }} className="mt-4 rounded-full border border-slate-200 px-4 py-2 text-xs font-black text-slate-700 hover:bg-slate-50">{label}</button>
                  </article>
                );
              })}
            </div>
          )}
        </SectionCard>

        <SectionCard title="Recommendation Cards" subtitle="Short explanations users can act on immediately.">
          <div className="grid gap-4 md:grid-cols-3">
            {cards.map((card) => (
              <div key={card.title} className={`rounded-[1.75rem] p-5 shadow-sm ${card.tone}`}>
                <h3 className="text-lg font-black">{card.title}</h3>
                <p className="mt-2 text-sm leading-6">{card.body}</p>
                <button type="button" onClick={() => { window.location.href = card.route; }} className="mt-4 rounded-full bg-white/75 px-4 py-2 text-xs font-black shadow-sm">{card.button}</button>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </AppLayout>
  );
}
