import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { signInWithGoogle, signUp } from "../actions";
import styles from "../auth.module.css";

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const t = await getTranslations();

  function getErrorMessage(errKey: string) {
    if (errKey === "signup_failed") {
      return t("auth.errors.signupFailed");
    }
    if (errKey === "oauth_failed") {
      return t("auth.errors.oauthFailed");
    }
    return t("auth.errors.default");
  }

  return (
    <div className={styles.pageWrapper}>
      <header className={styles.topBar}>
        <Link href="/" className={styles.homeButton}>
          <span aria-hidden="true">←</span>
          <span>{t("auth.backToHome")}</span>
        </Link>
      </header>

      <main className={styles.mainContainer}>
        <div className={styles.cardContainer}>
          <section className={styles.formCard} aria-labelledby="register-heading">
            <h1 id="register-heading" className={styles.formTitle}>
              {t("auth.registerHeading")}
            </h1>
            <p className={styles.formSubtitle}>{t("auth.registerSubheading")}</p>

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

            <form action={signUp} className={styles.authForm}>
              <div className={styles.fieldGroup}>
                <label htmlFor="register-email" className={styles.fieldLabel}>
                  <span>{t("auth.emailLabel")}</span>
                </label>
                <input
                  id="register-email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder={t("auth.emailPlaceholder")}
                  className={styles.inputControl}
                />
              </div>

              <div className={styles.fieldGroup}>
                <label htmlFor="register-password" className={styles.fieldLabel}>
                  <span>{t("auth.passwordLabel")}</span>
                  <span className={styles.fieldHint}>{t("auth.passwordMinLengthHint")}</span>
                </label>
                <input
                  id="register-password"
                  name="password"
                  type="password"
                  required
                  minLength={6}
                  autoComplete="new-password"
                  placeholder={t("auth.passwordPlaceholder")}
                  className={styles.inputControl}
                />
              </div>

              <button type="submit" className={styles.primaryButton}>
                {t("auth.registerSubmit")}
              </button>
            </form>

            <div className={styles.divider}>
              <span>{t("auth.or")}</span>
            </div>

            <form action={signInWithGoogle}>
              <button type="submit" className={styles.googleButton}>
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  aria-hidden="true"
                >
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <span>{t("auth.continueWithGoogle")}</span>
              </button>
            </form>

            <footer className={styles.cardFooter}>
              <span>{t("auth.haveAccountPrompt")} </span>
              <Link href="/login" className={styles.switchLink}>
                {t("auth.signInAction")}
              </Link>
            </footer>
          </section>
        </div>
      </main>
    </div>
  );
}