import { Link } from "react-router-dom";
import Brand from "./Brand";
import AppIcon from "./ui/AppIcon";

/** Frame authentication forms in the MoneyLeak technical visual system. */
export default function AuthShell({ eyebrow, title, subtitle, children, footer }) {
  return (
    <main className="auth-page min-h-screen">
      <img className="auth-page__art" src="/moneyleak-ai-logo.png" alt="" aria-hidden="true" />
      <header className="auth-page__header"><Link to="/"><Brand /></Link></header>
      <section className="auth-panel">
        <div className="technical-label"><span>{eyebrow}</span><span>SECURE SESSION</span></div>
        <div className="auth-icon"><AppIcon name="shield" size={21} /></div>
        <h1>{title}</h1>
        <p className="auth-panel__copy">{subtitle}</p>
        {children}
        <div className="auth-panel__footer">{footer}</div>
      </section>
    </main>
  );
}
