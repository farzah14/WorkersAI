import { describe, expect, it } from "vitest";
import { initialsFor, resolveDisplayName } from "@/lib/display-name";

describe("resolveDisplayName", () => {
  it("uses the email username and ignores the Google full name", () => {
    expect(
      resolveDisplayName({ user_metadata: { full_name: "Budi Santoso" }, email: "budi@gmail.com" }),
    ).toBe("budi");
  });

  it("uses the email username for plain email accounts", () => {
    expect(resolveDisplayName({ user_metadata: {}, email: "yantofarzah@gmail.com" })).toBe(
      "yantofarzah",
    );
  });

  it("falls back to Job Seeker when the user has no email", () => {
    expect(resolveDisplayName(null)).toBe("Job Seeker");
    expect(resolveDisplayName({ user_metadata: undefined, email: null })).toBe("Job Seeker");
  });

  it("falls back to Job Seeker for a blank or malformed email", () => {
    expect(resolveDisplayName({ user_metadata: {}, email: "   " })).toBe("Job Seeker");
    expect(resolveDisplayName({ user_metadata: {}, email: "@nousername.com" })).toBe("Job Seeker");
  });
});

describe("initialsFor", () => {
  it("builds initials from the first two words", () => {
    expect(initialsFor("Budi Santoso")).toBe("BS");
  });

  it("uses the first two characters of a username", () => {
    expect(initialsFor("yantofarzah")).toBe("YA");
  });

  it("falls back for empty input", () => {
    expect(initialsFor("")).toBe("JS");
  });
});