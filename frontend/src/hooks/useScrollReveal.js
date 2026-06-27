import { useEffect } from "react";

/** Add restrained scroll reveals to current and asynchronously rendered surfaces. */
export default function useScrollReveal(rootRef) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) {
      return undefined;
    }
    if (typeof IntersectionObserver === "undefined" || typeof MutationObserver === "undefined") {
      root.querySelectorAll("[data-reveal], main section").forEach((target) => target.classList.add("is-visible"));
      return undefined;
    }

    const observed = new WeakSet();
    let revealIndex = 0;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: "0px 0px -48px" });

    const observeTargets = () => {
      root.querySelectorAll("[data-reveal], main section").forEach((target) => {
        if (observed.has(target)) {
          return;
        }
        observed.add(target);
        target.classList.add("scroll-reveal");
        target.style.setProperty("--reveal-delay", `${Math.min(revealIndex % 5, 4) * 55}ms`);
        revealIndex += 1;
        observer.observe(target);
      });
    };

    observeTargets();
    const mutationObserver = new MutationObserver(observeTargets);
    mutationObserver.observe(root, { childList: true, subtree: true });
    return () => {
      mutationObserver.disconnect();
      observer.disconnect();
    };
  }, [rootRef]);
}
