import { useRef } from "react";
import { Link } from "react-router-dom";
import Brand from "../components/Brand";
import AppIcon from "../components/ui/AppIcon";
import useScrollReveal from "../hooks/useScrollReveal";

const FEATURES = [
  { number: "01", title: "Duplicate payment detection", description: "Catch repeated charges, similar merchant names, and suspicious payment timing.", icon: "copy" },
  { number: "02", title: "Recurring charge radar", description: "Surface subscriptions and recurring payments with confidence, frequency, and yearly impact.", icon: "repeat" },
  { number: "03", title: "Spending anomaly scan", description: "Compare unusual amounts and merchant behavior against your real transaction history.", icon: "activity" },
  { number: "04", title: "Savings action engine", description: "Turn detected leaks into ranked actions with monthly and annual savings potential.", icon: "target" }
];

const TICKER = ["DUPLICATES CAUGHT", "SUBSCRIPTIONS EXPOSED", "FEES IDENTIFIED", "SPENDING SCORED", "SAVINGS PROJECTED"];

/** Render the public MoneyLeak AI experience. */
export default function Home() {
  const rootRef = useRef(null);
  useScrollReveal(rootRef);

  return (
    <main ref={rootRef} className="public-site min-h-screen text-white">
      <header className="public-nav">
        <Link to="/" className="public-brand"><Brand /></Link>
        <nav className="flex items-center gap-2" aria-label="Public navigation">
          <Link to="/login" className="nav-text-link">Log in</Link>
          <Link to="/register" className="signal-button px-4 py-2.5 text-xs font-extrabold">Analyze statement <AppIcon name="transfer" size={14} /></Link>
        </nav>
      </header>

      <div className="signal-ticker" aria-label="MoneyLeak capabilities">
        <div className="signal-ticker__track">
          {[...TICKER, ...TICKER].map((item, index) => <span key={`${item}-${index}`}>{item}</span>)}
        </div>
      </div>

      <section className="hero-stage">
        <img className="hero-brand-art" src="/moneyleak-ai-logo.png" alt="" aria-hidden="true" />
        <div className="hero-stage__content">
          <div className="detection-ready"><span /> DETECTION ENGINE READY</div>
          <h1 className="hero-title mt-6">
            <span className="hero-title__line">Detect money leaks.</span>
            <span className="hero-title__line hero-title__line--signal">Keep more.</span>
          </h1>
          <p className="hero-copy mt-6 max-w-2xl">Upload a CSV or Excel bank statement. MoneyLeak AI cleans every transaction, finds hidden waste, and shows exactly what you can save.</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link to="/register" className="signal-button px-6 py-4 text-sm font-black">Upload statement <AppIcon name="upload" size={17} /></Link>
            <Link to="/login" className="outline-button px-6 py-4 text-sm font-black">Open dashboard <AppIcon name="chart" size={17} /></Link>
          </div>
          <div className="hero-trust mt-8">
            <span><AppIcon name="shield" size={15} /> No bank login</span>
            <span><AppIcon name="receipt" size={15} /> CSV or Excel only</span>
            <span><AppIcon name="search" size={15} /> Explainable findings</span>
          </div>
        </div>

        <div className="hero-readout" data-reveal>
          <div className="technical-label"><span>EXAMPLE SCAN</span><span>RUN 001</span></div>
          <div className="hero-score-row">
            <div><p>LEAK SCORE</p><strong>68</strong></div>
            <div><p>MONTHLY SAVING</p><strong>INR 4,850</strong></div>
          </div>
          <div className="scan-line"><span style={{ width: "68%" }} /></div>
          <div className="hero-findings">
            <p><AppIcon name="repeat" size={15} /> 3 recurring charges need review</p>
            <p><AppIcon name="copy" size={15} /> 2 possible duplicate payments</p>
            <p><AppIcon name="bank" size={15} /> INR 920 in avoidable fees</p>
          </div>
        </div>
      </section>

      <section className="proof-strip" data-reveal>
        <div><strong>100%</strong><span>transaction rows scanned</span></div>
        <div><strong>10 MB</strong><span>secure upload limit</span></div>
        <div><strong>17</strong><span>spending categories</span></div>
        <div><strong>1 hub</strong><span>complete money diagnosis</span></div>
      </section>

      <section className="public-section toolkit-section">
        <div className="section-kicker">THE DETECTION TOOLKIT</div>
        <div className="section-intro">
          <h2>Every leak.<br /><span>One system.</span></h2>
          <p>Not another generic budget chart. MoneyLeak AI names the merchant, charge, pattern, confidence, and annual cost so you know what to do next.</p>
        </div>
        <div className="feature-ledger">
          {FEATURES.map((feature) => (
            <article key={feature.number} className="feature-ledger__item" data-reveal>
              <span className="feature-number">{feature.number}</span>
              <span className="feature-icon"><AppIcon name={feature.icon} size={23} /></span>
              <div><h3>{feature.title}</h3><p>{feature.description}</p></div>
              <AppIcon name="transfer" size={18} className="feature-arrow" />
            </article>
          ))}
        </div>
      </section>

      <section className="public-section process-section">
        <div className="section-kicker">HOW THE ENGINE WORKS</div>
        <div className="process-grid">
          <article data-reveal><span>01 / INGEST</span><h3>Upload your statement.</h3><p>CSV, XLS, and XLSX files are validated before any transaction is processed.</p></article>
          <article data-reveal><span>02 / DIAGNOSE</span><h3>Scan every charge.</h3><p>Rules, merchant intelligence, and trained models clean, classify, and compare activity.</p></article>
          <article data-reveal><span>03 / ACT</span><h3>Recover your money.</h3><p>Review ranked leaks, correct categories, set budgets, and download a complete report.</p></article>
        </div>
      </section>

      <section className="final-cta" data-reveal>
        <div className="section-kicker">NO BANK PASSWORD REQUIRED</div>
        <h2>Find what your money<br />has been hiding.</h2>
        <p>Your first diagnosis starts with a statement export and takes minutes.</p>
        <Link to="/register" className="signal-button mt-7 px-7 py-4 text-sm font-black">Start analysis <AppIcon name="sparkles" size={17} /></Link>
      </section>

      <footer className="public-footer"><Brand compact /><span>DETECT / DIAGNOSE / SAVE</span><span>MoneyLeak AI</span></footer>
    </main>
  );
}
