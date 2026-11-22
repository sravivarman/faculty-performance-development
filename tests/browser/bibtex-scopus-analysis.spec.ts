import {expect, test} from "@playwright/test";

const bibtex = [
  "@article{doi, title={Scopus DOI Match}, author={Faculty, A}, journal={Source Journal}, year={2026}, doi={10.1234/scopus-match}}",
  "@article{fallback, title={Scopus Title Match}, author={Faculty, A}, journal={Source Journal}, year={2026}, date={2026-09-04}, doi={10.1234/bib-only}}",
].join("\n");
const scopus = [
  "EID,DOI,Title,Year,Document Type,Source title",
  "2-s2.0-1,https://doi.org/10.1234/SCOPUS-MATCH,Scopus DOI Match,2026,Article,Source Journal",
  "2-s2.0-2,,Scopus Title Match,2026,Article,Source Journal",
  "2-s2.0-3,10.1234/csv-only,CSV only,2026,Review,Source Journal",
].join("\n");

test("combined BibTeX and Scopus analysis presents source reconciliation without import controls", async ({page}) => {
  await page.goto("/publications/new");
  await page.getByRole("button", {name: "Upload BibTeX File", exact: true}).click();
  await page.getByLabel("BibTeX file", {exact: true}).setInputFiles({name: "records.bib", mimeType: "application/x-bibtex", buffer: Buffer.from(bibtex)});
  await page.getByLabel("Scopus CSV file (optional)", {exact: true}).setInputFiles({name: "records.csv", mimeType: "text/csv", buffer: Buffer.from(scopus)});
  await page.getByRole("button", {name: "Analyze BibTeX + Scopus CSV", exact: true}).click();
  await expect(page.getByText("Analysis Only — No Publications Have Been Saved", {exact: true})).toBeVisible();
  await expect(page.getByText("Unique source matches", {exact: true})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Import readiness", exact: true})).toBeVisible();
  const readinessSection = page.getByRole("heading", {name: "Import readiness", exact: true}).locator("..");
  const potentiallyNew = readinessSection.locator(".analysis-card").filter({hasText: "Potentially new — no duplicate detected"});
  await expect(potentiallyNew).toContainText("2");
  await expect(readinessSection.getByText("Missing exact dates", {exact: true})).toBeVisible();
  const readinessFilter = page.getByRole("combobox", {name: "Import readiness", exact: true});
  await expect(readinessFilter).toBeVisible();
  await readinessFilter.selectOption("DATE_VERIFICATION_REQUIRED");
  await expect(page.getByRole("row").filter({hasText: "Scopus DOI Match"})).toBeVisible();
  await expect(page.getByRole("row").filter({hasText: "Scopus Title Match"})).toHaveCount(0);
  await expect(potentiallyNew).toContainText("2");
  const sourceSection = page.getByRole("heading", {name: "Source reconciliation", exact: true}).locator("..");
  await expect(sourceSection.locator(".analysis-card").filter({hasText: "Unique source matches"})).toContainText("2");
  await expect(page.getByText("Scopus-only or ambiguous source records", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: /Add All Ready|Import selected|Save/})).toHaveCount(0);
  await page.getByRole("row").filter({hasText: "Scopus DOI Match"}).getByRole("button", {name: "Review", exact: true}).click();
  const details = page.getByRole("dialog", {name: "BibTeX entry 1 details", exact: true});
  await expect(details.getByRole("heading", {name: "Source matching", exact: true})).toBeVisible();
  await expect(details.getByRole("heading", {name: "Metadata comparison", exact: true})).toBeVisible();
  await expect(details.getByRole("heading", {name: "Import readiness checklist", exact: true})).toBeVisible();
  await expect(details.getByText("Not available in Stage 1D", {exact: true})).toBeVisible();
  await expect(details.getByText(/Matched Scopus CSV row 1 \(2-s2\.0-1\) by DOI/)).toBeVisible();
  await expect(details.getByRole("heading", {name: "Original BibTeX", exact: true})).toBeVisible();
});
