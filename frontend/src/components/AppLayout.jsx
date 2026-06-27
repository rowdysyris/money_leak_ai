import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import useScrollReveal from "../hooks/useScrollReveal";
import { useAuth } from "../context/AuthContext";
import Brand from "./Brand";
import AppIcon from "./ui/AppIcon";
import { useToast } from "./ui/Toast";

const NAV_ITEMS = [
  { path: "/dashboard", label: "Dashboard", icon: "chart" },
  { path: "/month-comparison", label: "Month Compare", icon: "calendar" },
  { path: "/financial-health", label: "Financial Health", icon: "health" },
  { path: "/goal-planner", label: "Goal Planner", icon: "target" },
  { path: "/upload", label: "Upload", icon: "upload" },
  { path: "/transactions", label: "Transactions", icon: "receipt" },
  { path: "/categories", label: "Categories", icon: "tag" },
  { path: "/smart-alerts", label: "Smart Alerts", icon: "alert" },
  { path: "/money-leaks", label: "Money Leaks", icon: "leak" },
  { path: "/subscriptions", label: "Subscriptions", icon: "repeat" },
  { path: "/budget", label: "Budget", icon: "wallet" },
  { path: "/reports", label: "Reports", icon: "file" },
  { path: "/ai-insights", label: "AI Insights", icon: "brain" }
];

function Navigation({ onNavigate }) {
  return (
    <nav className="app-navigation" aria-label="Application navigation">
      {NAV_ITEMS.map((item, index) => (
        <NavLink
          key={item.path}
          to={item.path}
          onClick={onNavigate}
          className={({ isActive }) => `app-nav-link ${isActive ? "is-active" : ""}`}
        >
          <span className="app-nav-index">{String(index + 1).padStart(2, "0")}</span>
          <AppIcon name={item.icon} size={17} />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

/** Render the authenticated MoneyLeak analysis workspace. */
export default function AppLayout({ children, title, subtitle }) {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const rootRef = useRef(null);
  useScrollReveal(rootRef);

  useEffect(() => {
    if (!mobileOpen) {
      return undefined;
    }
    const originalOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
      }
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [mobileOpen]);

  function handleLogout() {
    logout();
    showToast({ type: "success", message: "Logged out successfully." });
    navigate("/login");
  }

  return (
    <div ref={rootRef} className="app-shell min-h-screen text-slate-950">
      <aside className="desktop-sidebar fixed inset-y-0 left-0 z-40 hidden w-[268px] flex-col px-4 py-4 lg:flex">
        <Link to="/dashboard" className="sidebar-brand">
          <Brand />
        </Link>
        <div className="engine-status"><span className="engine-status__dot" /> ANALYSIS ENGINE ONLINE</div>
        <Navigation />
        <div className="user-console">
          <div className="flex items-center gap-3">
            <div className="user-console__avatar">{(user?.full_name ?? "ML").slice(0, 2).toUpperCase()}</div>
            <div className="min-w-0">
              <p className="truncate text-sm font-extrabold text-white">{user?.full_name ?? "MoneyLeak user"}</p>
              <p className="mt-0.5 truncate text-xs text-zinc-500">{user?.profile_type ?? "Profile"}</p>
            </div>
          </div>
          <button type="button" onClick={handleLogout} className="console-button mt-3 w-full">
            <AppIcon name="logout" size={15} /> Logout
          </button>
        </div>
      </aside>

      <header className="mobile-header sticky top-0 z-40 flex items-center justify-between px-4 py-3 lg:hidden">
        <Link to="/dashboard"><Brand compact /></Link>
        <button type="button" onClick={() => setMobileOpen((value) => !value)} className="icon-button" aria-label={mobileOpen ? "Close navigation" : "Open navigation"} aria-expanded={mobileOpen} aria-controls="mobile-app-navigation">
          <AppIcon name={mobileOpen ? "close" : "menu"} size={21} />
        </button>
      </header>

      {mobileOpen ? (
        <div id="mobile-app-navigation" role="dialog" aria-modal="true" aria-label="Application navigation" className="mobile-drawer fixed inset-x-0 bottom-0 top-[65px] z-30 overflow-y-auto p-4 lg:hidden">
          <Navigation onNavigate={() => setMobileOpen(false)} />
          <button type="button" onClick={handleLogout} className="console-button mt-4 w-full"><AppIcon name="logout" size={15} /> Logout</button>
        </div>
      ) : null}

      <main className="px-4 pb-12 pt-7 sm:px-6 lg:ml-[268px] lg:px-9 lg:pt-9 xl:px-12">
        {(title || subtitle) ? (
          <header className="page-heading mb-8" data-reveal>
            <div className="technical-label"><span>ML / ANALYSIS</span><span>LIVE DATA</span></div>
            <div className="mt-5 flex flex-col gap-4 border-b pb-7 sm:flex-row sm:items-end sm:justify-between">
              <div>
                {title ? <h1 className="page-title text-4xl font-black text-slate-950 sm:text-5xl">{title}</h1> : null}
                {subtitle ? <p className="mt-3 max-w-3xl text-sm font-medium leading-6 text-slate-500 sm:text-base">{subtitle}</p> : null}
              </div>
              <div className="live-badge"><span className="live-badge__pulse" /> LIVE ANALYSIS</div>
            </div>
          </header>
        ) : null}
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}
