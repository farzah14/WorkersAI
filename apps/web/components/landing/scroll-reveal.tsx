"use client";

import { useEffect, type ReactNode } from "react";

export function ScrollRevealProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    // If user prefers reduced motion, immediately reveal everything
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      document.querySelectorAll("[data-reveal]").forEach((el) => {
        el.setAttribute("data-revealed", "true");
      });
      return;
    }

    const revealElement = (el: Element) => {
      el.setAttribute("data-revealed", "true");
    };

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            revealElement(entry.target);
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.01,
        rootMargin: "0px 0px 60px 0px",
      }
    );

    const elements = document.querySelectorAll("[data-reveal]");
    elements.forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        revealElement(el);
      } else {
        observer.observe(el);
      }
    });

    // Handle smooth scrolling and target glow animation on clicking hash links
    const handleAnchorClick = (e: MouseEvent) => {
      const target = (e.target as HTMLElement).closest('a[href^="#"]');
      if (!target) return;
      const href = target.getAttribute("href");
      if (!href || href === "#") return;

      const targetElement = document.querySelector(href);
      if (targetElement) {
        e.preventDefault();

        // Immediately reveal all elements in the target section
        if (targetElement.hasAttribute("data-reveal")) {
          revealElement(targetElement);
        }
        targetElement.querySelectorAll("[data-reveal]").forEach((el) => {
          revealElement(el);
        });

        targetElement.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });

        // Trigger pulse highlight animation
        targetElement.classList.remove("sectionActiveGlow");
        // Force DOM reflow to re-trigger CSS animation
        void (targetElement as HTMLElement).offsetWidth;
        targetElement.classList.add("sectionActiveGlow");

        // Update URL hash without jarring jump
        window.history.pushState(null, "", href);
      }
    };

    // If page loaded with a hash, reveal that section immediately
    if (window.location.hash) {
      const targetSection = document.querySelector(window.location.hash);
      if (targetSection) {
        if (targetSection.hasAttribute("data-reveal")) {
          revealElement(targetSection);
        }
        targetSection.querySelectorAll("[data-reveal]").forEach((el) => {
          revealElement(el);
        });
      }
    }

    document.addEventListener("click", handleAnchorClick);

    return () => {
      observer.disconnect();
      document.removeEventListener("click", handleAnchorClick);
    };
  }, []);

  return <>{children}</>;
}
