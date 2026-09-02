import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const fixture = JSON.parse(
  readFileSync(fileURLToPath(new URL("../src/__fixtures__/proposal.json", import.meta.url)), "utf8"),
) as { id: string; proposal: { hero_headline: string } };

test("proposal page renders hero, a chart, and a mailto CTA", async ({ page }) => {
  await page.goto(`/p/${fixture.id}`);
  await expect(page.getByText(fixture.proposal.hero_headline)).toBeVisible();
  await expect(page.locator("svg").first()).toBeVisible();
  await expect(page.locator('a[href^="mailto:"]').first()).toBeVisible();
});

test("bad id shows the error state", async ({ page }) => {
  await page.goto("/p/not-a-uuid");
  await expect(page.getByText(/isn't valid or has expired/i)).toBeVisible();
});
