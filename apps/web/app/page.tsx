import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { LandingNav } from "@/components/landing/landing-nav";
import { ScrollRevealProvider } from "@/components/landing/scroll-reveal";
import styles from "./page.module.css";

export default async function Home() {
  const t = await getTranslations("landing");

  const scoreRows = [
    { label: t("score.skills"), weight: "35%", signal: t("score.strong") },
    { label: t("score.experience"), weight: "25%", signal: t("score.aligned") },
    { label: t("score.seniority"), weight: "15%", signal: t("score.aligned") },
    { label: t("score.education"), weight: "10%", signal: t("score.context") },
    { label: t("score.language"), weight: "8%", signal: t("score.context") },
    { label: t("score.location"), weight: "7%", signal: t("score.review") },
  ];

  const stages = [
    {
      number: "1.0",
      label: t("workflow.intake.label"),
      title: t("workflow.intake.title"),
      body: t("workflow.intake.body"),
      visualClass: styles.stageVisualIntake,
    },
    {
      number: "2.0",
      label: t("workflow.review.label"),
      title: t("workflow.review.title"),
      body: t("workflow.review.body"),
      visualClass: styles.stageVisualReview,
    },
    {
      number: "3.0",
      label: t("workflow.match.label"),
      title: t("workflow.match.title"),
      body: t("workflow.match.body"),
      visualClass: styles.stageVisualMatch,
    },
  ];

  return (
    <ScrollRevealProvider>
      <main className={styles.page} aria-labelledby="landing-title">
        <LandingNav />

        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <h1 id="landing-title">{t("hero.title")}</h1>
            <p className={styles.heroDescription}>{t("hero.description")}</p>
            <div className={styles.heroActions}>
              <Link href="/register" className={styles.primaryCta}>
                {t("hero.uploadCta")}
                <span className={styles.ctaArrow} aria-hidden="true">→</span>
              </Link>
              <a href="#workflow" className={styles.secondaryCta}>
                {t("hero.howItWorks")}
              </a>
            </div>
            <div className={styles.heroMeta} aria-label={t("hero.metaLabel")}>
              <div>
                <span>{t("hero.metaFormats")}</span>
                <strong>PDF · DOCX</strong>
              </div>
              <div>
                <span>{t("hero.metaSearch")}</span>
                <strong>Indonesia · Global</strong>
              </div>
              <div>
                <span>{t("hero.metaControl")}</span>
                <strong>{t("hero.metaControlValue")}</strong>
              </div>
            </div>
          </div>

          <div className={styles.heroProof}>
            <article className={styles.matchCard} aria-label={t("preview.ariaLabel")}>
              <div className={styles.matchTopline}>
                <span className={styles.cardEvidenceBadge}>{t("preview.label")}</span>
                <span className={styles.matchStatus}>
                  <span className={styles.statusDot} aria-hidden="true" />
                  {t("preview.status")}
                </span>
              </div>

              <div className={styles.matchHeading}>
                <div>
                  <p className={styles.roleSubcategory}>{t("preview.roleType")}</p>
                  <h2 className={styles.matchRoleTitle}>{t("preview.role")}</h2>
                </div>
                <div className={styles.scoreBadgeWrap}>
                  <span className={styles.scoreNumber}>{t("preview.scoreBadge")}</span>
                  <span className={styles.scoreNumberLabel}>{t("preview.scoreLabel")}</span>
                </div>
              </div>

              <div className={styles.matchBucketsRow}>
                <span className={styles.matchBucket}>{t("preview.bucket")}</span>
                <span className={styles.metaScopeTag}>{t("preview.locationValue")}</span>
              </div>

              <div className={styles.dimensionMiniBars}>
                <div className={styles.dimensionItem}>
                  <div className={styles.dimensionHeader}>
                    <span>{t("preview.skillsLabel")}</span>
                    <span className={styles.dimValue}>{t("preview.skillsValue")}</span>
                  </div>
                  <div className={styles.dimBarTrack}>
                    <div className={`${styles.dimBarFill} ${styles.dimFillSkills}`} style={{ width: "96%" }} />
                  </div>
                  <span className={styles.dimDetail}>{t("preview.skillsDetail")}</span>
                </div>

                <div className={styles.dimensionItem}>
                  <div className={styles.dimensionHeader}>
                    <span>{t("preview.expLabel")}</span>
                    <span className={styles.dimValue}>90%</span>
                  </div>
                  <div className={styles.dimBarTrack}>
                    <div className={`${styles.dimBarFill} ${styles.dimFillExp}`} style={{ width: "90%" }} />
                  </div>
                  <span className={styles.dimDetail}>{t("preview.expValue")}</span>
                </div>
              </div>

              <div className={styles.strengthTags}>
                <span className={styles.strengthChip}>✓ {t("preview.tag1")}</span>
                <span className={styles.strengthChip}>✓ {t("preview.tag2")}</span>
                <span className={styles.strengthChip}>✓ {t("preview.tag3")}</span>
                <span className={styles.strengthChip}>✓ {t("preview.tag4")}</span>
              </div>

              <div className={styles.recommendationBox}>
                <div className={styles.recHeader}>
                  <span className={styles.recIcon} aria-hidden="true">💡</span>
                  <span className={styles.recTitle}>{t("preview.recommendationTitle")}</span>
                </div>
                <p className={styles.recBody}>{t("preview.recommendationBody")}</p>
              </div>

              <Link href="/register" className={styles.matchCardCta}>
                <span>{t("preview.inspectAction")}</span>
                <span className={styles.ctaArrow} aria-hidden="true">→</span>
              </Link>
            </article>
          </div>
        </section>

        <section id="score" className={`${styles.section} ${styles.scoreSection}`}>
          <div className={styles.sectionHead} data-reveal="fade-up">
            <h2>{t("score.title")}</h2>
            <p>{t("score.description")}</p>
          </div>
          <div className={styles.scoreTable} role="table" aria-label={t("score.tableLabel")} data-reveal="fade-up">
            <div className={styles.scoreTableRow} role="row">
              <span role="columnheader">{t("score.dimensionHeader")}</span>
              <span role="columnheader">{t("score.weightHeader")}</span>
              <span role="columnheader">{t("score.signalHeader")}</span>
            </div>
            {scoreRows.map((row) => (
              <div className={styles.scoreTableRow} role="row" key={`table-${row.label}`}>
                <span role="cell">{row.label}</span>
                <span role="cell" className={styles.tableWeight}>
                  {row.weight}
                </span>
                <span role="cell" className={styles.tableSignal}>
                  {row.signal}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section id="workflow" className={`${styles.section} ${styles.workflowSection}`}>
          <div className={styles.sectionHead} data-reveal="fade-up">
            <h2>{t("workflow.title")}</h2>
            <p>{t("workflow.description")}</p>
          </div>
          <ol className={styles.workflowList}>
            {stages.map((stage) => (
              <li className={styles.workflowStage} key={stage.number} data-reveal="stagger">
                <span className={styles.stageNumber}>{stage.number}</span>
                <div className={styles.stageCopy}>
                  <p>{stage.label}</p>
                  <h3>{stage.title}</h3>
                  <span>{stage.body}</span>
                </div>
                <div className={`${styles.stageVisual} ${stage.visualClass}`} aria-hidden="true">
                  {stage.number === "1.0" && (
                    <>
                      <div className={styles.fileTab}>PDF</div>
                      <div className={styles.filePage}>
                        <span className={styles.fileTitle}>CV.pdf</span>
                        <span className={styles.fileLine} />
                        <span className={styles.fileLineShort} />
                        <span className={styles.fileLine} />
                        <span className={styles.fileLineMedium} />
                      </div>
                    </>
                  )}
                  {stage.number === "2.0" && (
                    <div className={styles.profilePreview}>
                      <div className={styles.profilePreviewTop}>
                        <span>{t("workflow.visualProfile")}</span>
                        <span className={styles.editBadge}>{t("workflow.visualEditable")}</span>
                      </div>
                      <span className={styles.profileLineWide} />
                      <span className={styles.profileLine} />
                      <span className={styles.profileLineMedium} />
                      <span className={styles.profileLineWide} />
                    </div>
                  )}
                  {stage.number === "3.0" && (
                    <div className={styles.jobPreview}>
                      <div>
                        <span>{t("workflow.visualMatch")}</span>
                        <strong>{t("workflow.visualStrong")}</strong>
                      </div>
                      <span className={styles.jobPreviewRule} />
                      <span className={styles.jobPreviewRuleShort} />
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section id="trust" className={styles.trustSection}>
          <div className={styles.trustInner}>
            <div className={styles.trustLead} data-reveal="fade-up">
              <h2>{t("trust.title")}</h2>
              <p>{t("trust.description")}</p>
            </div>
            <ul className={styles.trustList}>
              <li data-reveal="stagger">
                <span>01</span>
                <div>
                  <h3>{t("trust.controlTitle")}</h3>
                  <p>{t("trust.controlBody")}</p>
                </div>
              </li>
              <li data-reveal="stagger">
                <span>02</span>
                <div>
                  <h3>{t("trust.privacyTitle")}</h3>
                  <p>{t("trust.privacyBody")}</p>
                </div>
              </li>
              <li data-reveal="stagger">
                <span>03</span>
                <div>
                  <h3>{t("trust.boundaryTitle")}</h3>
                  <p>{t("trust.boundaryBody")}</p>
                </div>
              </li>
            </ul>
          </div>
        </section>

        <section className={styles.ctaSection} data-reveal="zoom-up">
          <div className={styles.ctaCopy}>
            <h2>{t("cta.title")}</h2>
            <p>{t("cta.description")}</p>
          </div>
          <Link href="/register" className={styles.ctaLink}>
            {t("cta.button")}
            <span className={styles.ctaArrow} aria-hidden="true">→</span>
          </Link>
        </section>

        <footer className={styles.footer} data-reveal="fade">
          <Link href="/" className={styles.footerBrand}>
            <span className={styles.wordmarkMark} aria-hidden="true" />
            Hirevia
          </Link>
          <span>{t("footer.tagline")}</span>
          <Link href="/login" className={styles.footerLink}>
            {t("footer.signIn")}
          </Link>
          <span>{t("footer.legal")}</span>
        </footer>
      </main>
    </ScrollRevealProvider>
  );
}
