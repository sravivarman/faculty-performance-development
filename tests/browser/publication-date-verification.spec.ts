import {expect, test} from "@playwright/test";

test("automatic publication-date verification shows evidence without an import action", async ({page}) => {
  let releaseResponse: (() => void) | undefined;
  let notifyRequest: (() => void) | undefined;
  let requestedDoi: string | undefined;
  const requestStarted = new Promise<void>(resolve => {notifyRequest = resolve;});
  const responseGate = new Promise<void>(resolve => {releaseResponse = resolve;});
  await page.route("**/api/publications/analyze-bibtex-file/enrich-dates", async route => {
    const payload = route.request().postDataJSON() as {entries?: {doi?: string}[]};
    requestedDoi = payload.entries?.[0]?.doi;
    notifyRequest?.();
    await responseGate;
    await route.fulfill({json: {
    analysis_only: true, requested: 1, results: [{entry_number: 1, doi: "10.1234/date-evidence", status: "FOUND", source: "CROSSREF",
      preferred: {date: "2025-03-15", precision: "DAY", date_type: "ONLINE", source_field: "published-online", is_exact_online: true},
      alternatives: [{date: "2025-03-15", precision: "DAY", date_type: "ONLINE", source_field: "published-online", is_exact_online: true}],
      verification: {identity_status: "VERIFIED_IDENTITY", suggestion_status: "EXACT_ONLINE_FOUND", requires_review: false, bibtex_date_conflict: false, provider_failures: [],
        suggested_date: {date: "2025-03-15", precision: "DAY", date_type: "ONLINE_PUBLICATION", source: "CROSSREF", source_field: "published-online", source_url: "https://api.crossref.org/works/10.1234/date-evidence", assessment: "EXACT_ONLINE"},
        candidates: [{date: "2025-03-15", precision: "DAY", date_type: "ONLINE_PUBLICATION", source: "CROSSREF", source_field: "published-online", source_url: "https://api.crossref.org/works/10.1234/date-evidence", assessment: "EXACT_ONLINE"}]},
    }],
    }});
  });
  await page.goto("/publications/new");
  await page.getByRole("button", {name: "Upload BibTeX File", exact: true}).click();
  await page.getByLabel("BibTeX file", {exact: true}).setInputFiles({name: "dates.bib", mimeType: "application/x-bibtex", buffer: Buffer.from("@article{date, title={Date evidence}, author={Faculty, A}, journal={Verification Journal}, year={2025}, doi={10.1234/date-evidence}}")});
  await page.getByRole("button", {name: "Analyze BibTeX File", exact: true}).click();
  await page.getByRole("button", {name: "Review", exact: true}).click();
  const analysisRegion = page.getByRole("region", {name: "Upload BibTeX File", exact: true});
  const details = page.getByRole("dialog", {name: "BibTeX entry 1 details", exact: true});
  await expect(details.getByRole("heading", {name: "Publication date review", exact: true})).toBeVisible();
  await details.getByRole("button", {name: "Verify this DOI automatically", exact: true}).click();
  await requestStarted;
  expect(requestedDoi).toBe("10.1234/date-evidence");
  const loadingStatus = details.getByRole("status").filter({hasText: /Verifying this DOI automatically/});
  try {
    await expect(loadingStatus).toBeVisible();
  } finally {
    releaseResponse?.();
  }
  await expect(loadingStatus).toHaveCount(0);
  await expect(details.getByText("Exact Online Found", {exact: true})).toBeVisible();
  await expect(details.getByRole("link", {name: "published-online", exact: true})).toBeVisible();
  await details.getByRole("button", {name: "Close details", exact: true}).click();
  await page.getByRole("button", {name: "Review", exact: true}).click();
  await expect(page.getByRole("dialog", {name: "BibTeX entry 1 details", exact: true}).getByText("Exact Online Found", {exact: true})).toBeVisible();
  await expect(analysisRegion.getByRole("button", {name: /^(Save|Import|Approve|Update)/i})).toHaveCount(0);
});
