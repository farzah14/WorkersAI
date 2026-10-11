"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { SENIORITIES, type CandidateProfile } from "@/lib/profile/schema";

function listToArray(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

type ProfileFormProps = {
  cvId: string;
  initial: CandidateProfile | null;
};

export function ProfileForm({ cvId, initial }: ProfileFormProps) {
  const router = useRouter();
  const t = useTranslations("profile.form");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [values, setValues] = useState({
    name: initial?.name ?? "",
    current_role: initial?.current_role ?? "",
    seniority: initial?.seniority ?? "unknown",
    target_roles: initial?.target_roles?.join(", ") ?? "",
    skills: initial?.skills?.join(", ") ?? "",
    experience_years: initial?.experience_years ?? "",
    languages: initial?.languages?.join(", ") ?? "",
    education: initial?.education?.join(", ") ?? "",
  });

  function set<K extends keyof typeof values>(key: K, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const response = await fetch("/api/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cv_id: cvId,
        profile: {
          name: values.name,
          current_role: values.current_role,
          seniority: values.seniority,
          target_roles: listToArray(values.target_roles),
          skills: listToArray(values.skills),
          experience_years: values.experience_years === "" ? undefined : Number(values.experience_years),
          languages: listToArray(values.languages),
          education: listToArray(values.education),
        },
      }),
    });
    setSaving(false);
    if (!response.ok) {
      const data = (await response.json().catch(() => null)) as { error?: string } | null;
      setError(
        data?.error === "active_cv_conflict"
          ? t("activeConflict")
          : data?.error === "save_conflict"
            ? t("saveConflict")
            : data?.error === "validation_failed"
              ? t("validationError")
              : (data?.error ?? t("genericError")),
      );
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm">
        {t("name")}
        <input
          value={values.name}
          onChange={(event) => set("name", event.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("currentRole")}
        <input
          value={values.current_role}
          onChange={(event) => set("current_role", event.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("seniority")}
        <select
          value={values.seniority}
          onChange={(event) => set("seniority", event.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        >
          {SENIORITIES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("targetRoles")}
        <input
          value={values.target_roles}
          onChange={(event) => set("target_roles", event.target.value)}
          required
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("skills")}
        <input
          value={values.skills}
          onChange={(event) => set("skills", event.target.value)}
          required
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("experienceYears")}
        <input
          value={values.experience_years}
          onChange={(event) => set("experience_years", event.target.value)}
          type="number"
          min={0}
          max={80}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("languages")}
        <input
          value={values.languages}
          onChange={(event) => set("languages", event.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("education")}
        <input
          value={values.education}
          onChange={(event) => set("education", event.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={saving}
        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {saving ? t("savingButton") : t("saveButton")}
      </button>
    </form>
  );
}
