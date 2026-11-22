import {expect, test} from "@playwright/test";

const bibtex = "@article{candidate, title={Review candidate}, author={Review Confirmed Faculty}, journal={Review Journal}, year={2026}, doi={10.1234/review-candidate}}";

test("bulk review workspace exports and restores a reviewed browser-only Journal draft", async ({page, request}) => {
  const mastersResponse = await request.get("/api/masters");
  expect(mastersResponse.ok()).toBeTruthy();
  const masters = await mastersResponse.json() as {departments: {id: number; code: string; is_active: boolean}[]};
  const department = masters.departments.find(item => item.is_active);
  if (!department) throw new Error("Bulk review browser fixtures require an active Department Master record.");
  const createFaculty = async (employeeId: string, name: string) => {
    const response = await request.post("/api/faculty", {data: {employee_id: employeeId, name, department_id: department.id, department_effective_from: "2026-07-01"}});
    expect(response.status()).toBe(201);
    return response.json() as Promise<{id: number; employee_id: string; name: string}>;
  };
  const confirmedFaculty = await createFaculty("REVIEW-E2E-CONFIRMED", "Review Confirmed Faculty");
  const unrelatedFaculty = await createFaculty("REVIEW-E2E-UNRELATED", "Review Unrelated Faculty");
  await page.route("**/api/publications/analyze-bibtex-file/enrich-dates", async route => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({results: [{
      entry_number: 1, doi: "10.1234/review-candidate", status: "FOUND", verification: {
        identity_status: "VERIFIED_IDENTITY", suggestion_status: "EXACT_ONLINE_FOUND", requires_review: false,
        candidates: [{date: "2026-02-03", precision: "DAY", date_type: "PUBLISHED_ONLINE", source: "Crossref", source_field: "published-online", source_url: "https://doi.org/10.1234/review-candidate", assessment: "EXACT"}],
        suggested_date: {date: "2026-02-03", precision: "DAY", date_type: "PUBLISHED_ONLINE", source: "Crossref", source_field: "published-online", source_url: "https://doi.org/10.1234/review-candidate", assessment: "EXACT"}, provider_failures: [],
      },
    }]})});
  });
  await page.goto("/publications/new");
  await page.getByRole("button", {name: "Upload BibTeX File", exact: true}).click();
  await page.getByLabel("BibTeX file", {exact: true}).setInputFiles({name: "review-candidate.bib", mimeType: "application/x-bibtex", buffer: Buffer.from(bibtex)});
  await page.getByRole("button", {name: "Analyze BibTeX File", exact: true}).click();
  await page.getByRole("button", {name: "Open Bulk Review Workspace", exact: true}).click();
  const workspace = page.getByRole("region", {name: "Bulk publication review workspace", exact: true});
  await expect(workspace.getByText("Review Preparation Only — No Publications Have Been Saved", {exact: true})).toBeVisible();
  await expect(workspace.getByRole("row").filter({hasText: "Review candidate"})).toBeVisible();
  await workspace.getByLabel("Select Review candidate", {exact: true}).check();
  await workspace.getByRole("button", {name: /Verify selected DOI records \(1\)/}).click();
  await expect(workspace.getByText(/Requested DOI verification for 1 selected record/)).toBeVisible();
  await workspace.getByRole("row").filter({hasText: "Review candidate"}).getByRole("button", {name: "Review", exact: true}).click();
  const review = workspace.getByRole("dialog", {name: "Review Review candidate", exact: true});
  await review.getByLabel("Title", {exact: true}).fill("Reviewed candidate title");
  await review.getByLabel("Manual date evidence source", {exact: true}).fill("Publisher landing page");
  await review.getByLabel("Proposed publication date", {exact: true}).fill("2026-02-03");
  const contributor = review.getByLabel("Contributor 1", {exact: true});
  const claimant = review.getByLabel("Claiming Faculty for review", {exact: true});
  const confirmedOption = contributor.locator(`option[value="FACULTY:${confirmedFaculty.id}"]`);
  await expect(confirmedOption).toHaveText(`Faculty · ${confirmedFaculty.name} (${confirmedFaculty.employee_id}) · ${department.code}`);
  await expect(review.getByRole("cell", {name: /EXACT/})).toBeVisible();
  // Exact source matching starts as a confirmed contributor. Explicitly clear
  // it first to exercise the claimant-ineligibility safeguard.
  await contributor.selectOption("UNRESOLVED:");
  await expect(claimant.getByRole("option")).toHaveCount(1);
  await contributor.selectOption(`FACULTY:${confirmedFaculty.id}`);
  await expect(claimant.getByRole("option", {name: confirmedFaculty.name, exact: true})).toHaveCount(1);
  await expect(claimant.getByRole("option", {name: unrelatedFaculty.name, exact: true})).toHaveCount(0);
  await claimant.selectOption(String(confirmedFaculty.id));
  await review.getByRole("checkbox", {name: "contributors", exact: true}).check();
  await review.getByRole("checkbox", {name: "claimant", exact: true}).check();
  await contributor.selectOption(`FACULTY:${unrelatedFaculty.id}`);
  await expect(claimant).toHaveValue("");
  await expect(review.getByRole("checkbox", {name: "contributors", exact: true})).not.toBeChecked();
  await expect(review.getByRole("checkbox", {name: "claimant", exact: true})).not.toBeChecked();
  await contributor.selectOption(`FACULTY:${confirmedFaculty.id}`);
  await claimant.selectOption(String(confirmedFaculty.id));
  for (const step of ["identity", "duplicate", "classification", "metadata", "date", "contributors", "claimant"]) await review.getByRole("checkbox", {name: step, exact: true}).check();
  await expect(review.getByRole("button", {name: "Validate for Stage 2B", exact: true})).toBeEnabled();
  await review.getByRole("button", {name: "Validate for Stage 2B", exact: true}).click();
  await expect(review.getByText("VALIDATED_FOR_STAGE_2B", {exact: true})).toBeVisible();
  await expect(review.getByText("Original source metadata and review proposal", {exact: true})).toBeVisible();
  await expect(workspace.getByRole("button", {name: /Save|Approve|Add All Ready/})).toHaveCount(0);
  const download = page.waitForEvent("download");
  await workspace.getByRole("button", {name: "Export Review Session", exact: true}).click();
  const packagePath = await (await download).path();
  expect(packagePath).toBeTruthy();
  await workspace.getByRole("button", {name: "Delete local review data", exact: true}).click();
  await page.reload();
  await page.getByRole("button", {name: "Upload BibTeX File", exact: true}).click();
  await page.getByLabel("BibTeX file", {exact: true}).setInputFiles({name: "review-candidate.bib", mimeType: "application/x-bibtex", buffer: Buffer.from(bibtex)});
  await page.getByRole("button", {name: "Analyze BibTeX File", exact: true}).click();
  await page.getByRole("button", {name: "Open Bulk Review Workspace", exact: true}).click();
  const restoredWorkspace = page.getByRole("region", {name: "Bulk publication review workspace", exact: true});
  await restoredWorkspace.getByLabel("Import Review Session package", {exact: true}).setInputFiles(packagePath!);
  await expect(restoredWorkspace.getByText(/Restored review package/)).toBeVisible();
  await expect(restoredWorkspace.getByText(/Review package was rejected/)).toHaveCount(0);
  await restoredWorkspace.getByRole("row").filter({hasText: "Reviewed candidate title"}).getByRole("button", {name: "Review", exact: true}).click();
  const restoredReview = restoredWorkspace.getByRole("dialog", {name: "Review Review candidate", exact: true});
  await expect(restoredReview.getByLabel("Proposed publication date", {exact: true})).toHaveValue("2026-02-03");
  await expect(restoredReview.getByLabel("Claiming Faculty for review", {exact: true})).toHaveValue(String(confirmedFaculty.id));
  await expect(restoredReview.getByText("VALIDATED_FOR_STAGE_2B", {exact: true})).toBeVisible();
});

test("bulk review workspace rejects an untrusted session package", async ({page}) => {
  await page.goto("/publications/new");
  await page.getByRole("button", {name: "Upload BibTeX File", exact: true}).click();
  await page.getByLabel("BibTeX file", {exact: true}).setInputFiles({name: "untrusted.bib", mimeType: "application/x-bibtex", buffer: Buffer.from(bibtex)});
  await page.getByRole("button", {name: "Analyze BibTeX File", exact: true}).click();
  await page.getByRole("button", {name: "Open Bulk Review Workspace", exact: true}).click();
  const workspace = page.getByRole("region", {name: "Bulk publication review workspace", exact: true});
  await workspace.getByLabel("Import Review Session package", {exact: true}).setInputFiles({name: "untrusted.json", mimeType: "application/json", buffer: Buffer.from('{"package":{"schema":"wrong"}}')});
  await expect(workspace.getByText(/Review package was rejected/)).toBeVisible();
  await expect(workspace.getByText(/INVALID_PACKAGE_STRUCTURE/)).toBeVisible();
});
