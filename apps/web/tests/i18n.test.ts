import { describe, expect, it } from "vitest";
import idMessages from "@/messages/id.json";
import enMessages from "@/messages/en.json";
import { routing } from "@/i18n/routing";

type MessageNode = string | { [key: string]: MessageNode };

function collectKeys(node: MessageNode, prefix = ""): string[] {
  if (typeof node === "string") {
    return prefix ? [prefix] : [];
  }
  return Object.entries(node).flatMap(([key, value]) =>
    collectKeys(value, prefix ? `${prefix}.${key}` : key),
  );
}

describe("i18n message parity", () => {
  it("exposes exactly id and en locales with id as default", () => {
    expect(routing.locales).toEqual(["id", "en"]);
    expect(routing.defaultLocale).toBe("id");
  });

  it("has identical key sets in id and en messages", () => {
    const idKeys = collectKeys(idMessages as MessageNode).sort();
    const enKeys = collectKeys(enMessages as MessageNode).sort();
    expect(idKeys).toEqual(enKeys);
  });

  it("uses only string leaf values in messages", () => {
    const assertStrings = (node: MessageNode, path: string): void => {
      if (typeof node === "string") return;
      for (const [key, value] of Object.entries(node)) {
        if (typeof value === "object" && value !== null && !Array.isArray(value)) {
          assertStrings(value, `${path}.${key}`);
        } else if (typeof value !== "string") {
          throw new Error(`non-string leaf at ${path}.${key}`);
        }
      }
    };
    assertStrings(idMessages as MessageNode, "id");
    assertStrings(enMessages as MessageNode, "en");
  });

  it("covers the MVP UI key set required by the plan", () => {
    const required = [
      "nav.dashboard",
      "nav.saved",
      "nav.applications",
      "nav.exports",
      "nav.findJobs",
      "buckets.best",
      "buckets.strong",
      "buckets.potential",
      "buckets.low",
      "dimensions.skills",
      "dimensions.experience",
      "dimensions.seniority",
      "dimensions.education",
      "dimensions.language",
      "dimensions.location",
      "match.strengths",
      "match.gaps",
      "match.criticalGaps",
      "match.explanation",
      "match.recommendations",
      "match.verdict",
      "tracking.new",
      "tracking.saved",
      "tracking.applied",
      "tracking.ignored",
      "exports.title",
      "exports.xlsx",
      "exports.pdf",
      "settings.language",
    ];
    const idKeys = new Set(collectKeys(idMessages as MessageNode));
    for (const key of required) {
      expect(idKeys.has(key), `missing key: ${key}`).toBe(true);
    }
  });
});