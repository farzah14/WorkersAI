const allowed = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);
const MAX_BYTES = 10 * 1024 * 1024;

export function validateCvFile(file: { type: string; size: number }) {
  if (!allowed.has(file.type)) return { ok: false as const, error: "Only PDF and DOCX are supported." };
  if (file.size > MAX_BYTES) return { ok: false as const, error: "CV must be 10 MiB or smaller." };
  return { ok: true as const };
}