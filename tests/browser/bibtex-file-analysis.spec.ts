import {expect, test} from "@playwright/test";

const article = (key: string, title: string, doi: string) => `@article{${key}, title={${title}}, author={Faculty, A}, journal={Upload Journal}, year={2026}, date={2026-09-18}, doi={${doi}}}`;

test("BibTeX file upload analyzes a paged review without importing publications", async ({page}) => {
  await page.goto("/publications/new");
  await page.getByRole("button", {name: "Upload BibTeX File", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Upload BibTeX File", exact: true})).toBeVisible();
  const content = Array.from({length: 27}, (_, index) => article(`upload${index + 1}`, `Uploaded analysis ${index + 1}`, `10.1234/upload-analysis-${index + 1}`)).join("\n");
  await page.getByLabel("BibTeX file", {exact: true}).setInputFiles({name: "review.bib", mimeType: "application/x-bibtex", buffer: Buffer.from(content)});
  await page.getByRole("button", {name: "Analyze BibTeX File", exact: true}).click();
  await expect(page.getByText("Analysis Only — No Publications Have Been Saved", {exact: true})).toBeVisible();
  await expect(page.getByText("27 entries detected", {exact: false})).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(26);
  await page.getByRole("button", {name: "Next", exact: true}).click();
  await expect(page.getByText("Showing 26–27 of 27 matching entries", {exact: true})).toBeVisible();
  await page.getByRole("row").filter({hasText: "Uploaded analysis 26"}).getByRole("button", {name: "Review", exact: true}).click();
  await expect(page.getByRole("dialog", {name: /BibTeX entry .* details/})).toBeVisible();
  await expect(page.getByText("Original BibTeX", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: /Add All Ready/})).toHaveCount(0);
  await page.getByRole("button", {name: "Clear analysis", exact: true}).click();
  await expect(page.getByText("Analysis Only — No Publications Have Been Saved", {exact: true})).toHaveCount(0);
});

test("BibTeX file upload reports an unsupported extension without saving", async ({page}) => {
  await page.goto("/publications/new");
  await page.getByRole("button", {name: "Upload BibTeX File", exact: true}).click();
  await page.getByLabel("BibTeX file", {exact: true}).setInputFiles({name: "not-bib.txt", mimeType: "text/plain", buffer: Buffer.from("@article{x, title={Nope}}")});
  await page.getByRole("button", {name: "Analyze BibTeX File", exact: true}).click();
  await expect(page.getByRole("alert").filter({hasText: "Upload a .bib BibTeX file."})).toContainText("Upload a .bib BibTeX file.");
});
