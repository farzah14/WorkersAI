import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { requestPasswordReset } from "../actions";
import styles from "../auth.module.css";

export default async function ForgotPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; success?: string }>;
}) {
  const { error, success } = await searchParams;
  const t = await getTranslations();

  function getErrorMessage(errKey: string) {
    if (errKey === "missing_email") {
      return t("auth.errors.missingEmail");
    }
    if (errKey === "rate_limited") {
      return t("auth.errors.rateLimited");
    }
    if (errKey === "reset_failed") {
      return t("auth.errors.resetFailed");
    }
    return t("auth.errors.default");
  }

  return (
    <div className={styles.pageWrapper}>
      <header className={styles.topBar}>
        <Link href="/login" className={styles.homeButton}>
          <span aria-hidden="true">←</span>
          <span>{t("auth.signInAction")}</span>
        </Link>
      </header>

      <main className={styles.mainContainer}>
        <div className={styles.cardContainer}>
          <section className={styles.formCard} aria-labelledby="forgot-password-heading">
            <h1 id="forgot-password-heading" className={styles.formTitle}>
              {t("auth.forgotPasswordHeading")}
            </h1>
            <p className={styles.formSubtitle}>{t("auth.forgotPasswordSubheading")}</p>

            {success === "1" && (
              <div className={styles.successAlert} role="status">
                <svg
                  className={styles.successIcon}
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.7-9.3a1 1 0 00-1.4-1.4L9 10.6 7.7 9.3a1 1 0 00-1.4 1.4l2 2a1 1 0 001.4 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                <div>
                  <p className={styles.successDescription}>{t("auth.resetLinkSent")}</p>
                </div>
              </div>
            )}

            {error && (
              <div className={styles.errorAlert} role="alert">
                <svg
                  className={styles.errorIcon}
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                    clipRule="evenodd"
                  />
                </svg>
                <div>
                  <p className={styles.errorTitle}>{t("auth.errorTitle")}</p>
                  <p className={styles.errorDescription}>{getErrorMessage(error)}</p>
                </div>
              </div>
            )}

            <form action={requestPasswordReset} className={styles.authForm}>
              <div className={styles.fieldGroup}>
                <label htmlFor="reset-email" className={styles.fieldLabel}>
                  <span>{t("auth.emailLabel")}</span>
                </label>
                <input
                  id="reset-email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder={t("auth.emailPlaceholder")}
                  className={styles.inputControl}
                />
              </div>

              <button type="submit" className={styles.primaryButton}>
                {t("auth.sendResetLink")}
              </button>
            </form>

            <footer className={styles.cardFooter}>
              <p className={styles.footerPrompt}>{t("auth.haveAccountPrompt")}</p>
              <Link href="/login" className={styles.footerAction}>
                {t("auth.signInAction")}
              </Link>
            </footer>
          </section>
        </div>
      </main>
    </div>
  );
}
