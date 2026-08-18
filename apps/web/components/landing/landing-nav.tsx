"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import styles from "@/app/page.module.css";

export function LandingNav() {
  const t = useTranslations("landing.nav");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  return (
    <div className={styles.navWrap}>
      <nav className={styles.nav} aria-label={t("primary")}>
        <Link
          href="/"
          className={styles.wordmark}
          aria-label={t("home")}
          onClick={() => setIsOpen(false)}
        >
          <span className={styles.wordmarkMark} aria-hidden="true" />
          Hirevia
        </Link>

        {/* Desktop Navigation Links */}
        <div className={styles.navLinks}>
          <a href="#workflow" className={styles.navLink}>
            {t("howItWorks")}
          </a>
          <a href="#trust" className={styles.navLink}>
            {t("whyTrust")}
          </a>
          <Link href="/login" className={styles.navLink}>
            {t("signIn")}
          </Link>
        </div>

        {/* Action Buttons & Mobile Hamburger */}
        <div className={styles.navActions}>
          <Link href="/register" className={styles.navCta}>
            <span className={styles.navCtaWide}>{t("uploadCv")}</span>
            <span className={styles.navCtaCompact}>{t("start")}</span>
          </Link>

          <button
            type="button"
            className={styles.hamburgerBtn}
            onClick={() => setIsOpen((prev) => !prev)}
            aria-expanded={isOpen}
            aria-label={isOpen ? t("closeMenu") : t("openMenu")}
            aria-controls="mobile-nav-menu"
          >
            <span
              className={`${styles.hamburgerIcon} ${isOpen ? styles.hamburgerIconOpen : ""}`}
              aria-hidden="true"
            >
              <span className={styles.hamburgerBar} />
              <span className={styles.hamburgerBar} />
              <span className={styles.hamburgerBar} />
            </span>
          </button>
        </div>
      </nav>

      {/* Mobile Drawer Menu */}
      {isOpen && (
        <>
          <div
            className={styles.mobileBackdrop}
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div
            id="mobile-nav-menu"
            className={styles.mobileMenu}
            role="dialog"
            aria-modal="true"
            aria-label={t("primary")}
          >
            <div className={styles.mobileLinks}>
              <a
                href="#workflow"
                className={styles.mobileLink}
                onClick={() => setIsOpen(false)}
              >
                {t("howItWorks")}
              </a>
              <a
                href="#trust"
                className={styles.mobileLink}
                onClick={() => setIsOpen(false)}
              >
                {t("whyTrust")}
              </a>
              <Link
                href="/login"
                className={styles.mobileLink}
                onClick={() => setIsOpen(false)}
              >
                {t("signIn")}
              </Link>
              <Link
                href="/register"
                className={styles.mobileCta}
                onClick={() => setIsOpen(false)}
              >
                {t("uploadCv")}
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
