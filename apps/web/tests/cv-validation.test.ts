import { describe, expect, it } from "vitest";
import { validateCvFile } from "@/lib/cv/validation";

describe("validateCvFile", () => {
  it("accepts digital PDF and DOCX MIME types", () => {
    expect(validateCvFile({ type: "application/pdf", size: 1000 })).toEqual({ ok: true });
    expect(validateCvFile({ type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", size: 1000 })).toEqual({ ok: true });
  });
  it("rejects images and files over 10 MiB", () => {
    expect(validateCvFile({ type: "image/png", size: 1000 }).ok).toBe(false);
    expect(validateCvFile({ type: "application/pdf", size: 11 * 1024 * 1024 }).ok).toBe(false);
  });
});