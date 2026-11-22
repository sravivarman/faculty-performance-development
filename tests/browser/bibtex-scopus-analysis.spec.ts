import {expect, test} from "@playwright/test";

const bibtex = [
  "@article{doi, title={Scopus DOI Match}, author={Faculty, A}, journal={Source Journal}, year={2026}, doi={10.1234/scopus-match}}",
  "@article{fallback, title={Scopus Title Match}, author={Faculty, A}, journal={Source Journal}, year={2026}, doi={10.1234/bib-only}}",
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
  await expect(page.getByText("Unique CSV matches", {exact: true})).toBeVisible();
  await expect(page.getByText("Scopus-only or ambiguous source records", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: /Add All Ready|Import selected|Save/})).toHaveCount(0);
  await page.getByRole("row").filter({hasText: "Scopus DOI Match"}).getByRole("button", {name: "Review", exact: true}).click();
  const details = page.getByRole("dialog", {name: "BibTeX entry 1 details", exact: true});
  await expect(details.getByRole("heading", {name: "Source reconciliation", exact: true})).toBeVisible();
  await expect(details.getByText(/Matched Scopus CSV row 1 \(2-s2\.0-1\) by DOI/)).toBeVisible();
  await expect(details.getByRole("heading", {name: "Original BibTeX", exact: true})).toBeVisible();
});
