import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const supabaseConfig = readFileSync(
  resolve(process.cwd(), "../../supabase/config.toml"),
  "utf8",
);

describe("local OAuth redirects", () => {
  it("allows the callback for both local app hosts", () => {
    expect(supabaseConfig).toContain('"http://localhost:3000/auth/callback"');
    expect(supabaseConfig).toContain('"http://127.0.0.1:3000/auth/callback"');
  });
});
