import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { readdir } from "node:fs/promises";
import path from "node:path";

type RecordKind = "journal" | "conference" | "patent" | "book" | "chapter";
type Fixture = { kind: RecordKind; id: number; title: string; path: string; api: string };

test.describe.configure({ mode: "serial" });

function inside(child: string, parent: string) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

async function verifyIsolatedStorage(request: APIRequestContext) {
  const health = await (await request.get("/api/health")).json() as { database_path: string; evidence_path: string };
  const root = path.resolve(".test-tmp-e2e");
  const productionDatabase = path.resolve("data/faculty.db");
  const productionEvidence = path.resolve("storage/evidence");
  expect(path.resolve(health.database_path)).not.toBe(productionDatabase);
  expect(path.resolve(health.evidence_path)).not.toBe(productionEvidence);
  expect(inside(path.resolve(health.database_path), root)).toBeTruthy();
  expect(inside(path.resolve(health.evidence_path), root)).toBeTruthy();
}

async function evidenceFileCount(directory: string) {
  try {
    return (await readdir(directory, { recursive: true, withFileTypes: true })).filter((entry) => entry.isFile()).length;
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return 0;
    throw error;
  }
}

async function createPeople(request: APIRequestContext, suffix: string) {
  const facultyResponse = await request.post("/api/faculty", { data: { employee_id: `E2E-DELETE-F-${suffix}`, name: `E2E Delete Faculty ${suffix}` } });
  const studentResponse = await request.post("/api/students", { data: { roll_number: `E2E-DELETE-S-${suffix}`, name: `E2E Delete Student ${suffix}` } });
  expect(facultyResponse.ok()).toBeTruthy();
  expect(studentResponse.ok()).toBeTruthy();
  return { faculty: await facultyResponse.json(), student: await studentResponse.json() };
}

async function createRecord(request: APIRequestContext, kind: RecordKind, suffix: string, faculty: { id: number; name: string }, student: { id: number; name: string }): Promise<Fixture> {
  const title = `E2E DELETE ${kind.toUpperCase()} ${suffix}`;
  if (kind === "journal" || kind === "conference") {
    const response = await request.post("/api/publications", { data: {
      doi: `10.1234/e2e-delete-${kind}-${suffix.toLowerCase()}`,
      title,
      publication_type: kind === "journal" ? "JOURNAL" : "CONFERENCE",
      publication_date: "2026-08-15",
      journal_conference_name: kind === "journal" ? "E2E Journal" : "E2E Conference",
      conference_name: kind === "conference" ? "E2E Conference" : null,
      indexing: ["SCOPUS"],
      authors: [
        { author_order: 1, author_name_from_source: faculty.name, affiliation_from_source: [], person_type: "FACULTY", faculty_id: faculty.id, student_id: null, is_claiming_faculty: true, is_first_author: true },
        { author_order: 2, author_name_from_source: student.name, affiliation_from_source: [], person_type: "STUDENT", faculty_id: null, student_id: student.id },
      ],
    } });
    expect(response.ok()).toBeTruthy();
    const record = await response.json();
    return { kind, id: record.id, title, path: `/publications/${record.id}`, api: `/api/publications/${record.id}` };
  }
  if (kind === "patent") {
    const response = await request.post("/api/patents", { data: {
      title, application_number: `E2E-DELETE-${suffix}`, patent_office: "Indian Patent Office", country: "India", patent_type: "UTILITY", current_status: "FILED", filing_date: "2026-08-15",
      inventors: [
        { inventor_order: 1, inventor_name: faculty.name, person_type: "FACULTY", institution_scope: "CURRENT_DEPARTMENT", faculty_id: faculty.id, student_id: null, is_claiming_faculty: true },
        { inventor_order: 2, inventor_name: student.name, person_type: "STUDENT", institution_scope: "CURRENT_DEPARTMENT", faculty_id: null, student_id: student.id, is_claiming_faculty: false },
      ],
    } });
    expect(response.ok()).toBeTruthy();
    const record = await response.json();
    return { kind, id: record.id, title, path: `/patents/${record.id}`, api: `/api/patents/${record.id}` };
  }
  const chapter = kind === "chapter";
  const response = await request.post("/api/books", { data: {
    work_type: chapter ? "BOOK_CHAPTER" : "BOOK", title, parent_book_title: chapter ? "E2E Parent Book" : null, page_range: chapter ? "1-12" : null,
    publisher: "E2E Press", publication_date: "2026-08-15", doi: `10.1234/e2e-delete-${kind}-${suffix.toLowerCase()}`,
    contributors: [
      { contributor_order: 1, contributor_name: faculty.name, role: "AUTHOR", person_type: "FACULTY", institution_scope: "CURRENT_DEPARTMENT", faculty_id: faculty.id, student_id: null, is_claiming_faculty: true },
      { contributor_order: 2, contributor_name: student.name, role: "AUTHOR", person_type: "STUDENT", institution_scope: "CURRENT_DEPARTMENT", faculty_id: null, student_id: student.id, is_claiming_faculty: false },
    ],
  } });
  expect(response.ok()).toBeTruthy();
  const record = await response.json();
  return { kind, id: record.id, title, path: `/books/${record.id}`, api: `/api/books/${record.id}` };
}

async function acceptDeactivate(page: Page) {
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Deactivate", exact: true }).click();
}

async function openDetail(page: Page, record: Fixture) {
  await page.goto(record.path);
  await expect(page.getByRole("heading", { name: record.title, exact: true })).toBeVisible();
}

async function deleteThroughDialog(page: Page, record: Fixture, cancel = false) {
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: new RegExp(`Delete ${record.kind === "journal" || record.kind === "conference" ? "Publication" : record.kind === "patent" ? "Patent" : record.kind === "chapter" ? "Book Chapter" : "Book"}\?`) });
  await expect(dialog).toContainText(record.title);
  const confirm = dialog.getByRole("button", { name: "Delete", exact: true });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel("Type DELETE to confirm").fill("DELETEE");
  await expect(confirm).toBeDisabled();
  if (cancel) {
    await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    return;
  }
  await dialog.getByLabel("Type DELETE to confirm").fill("DELETE");
  await expect(confirm).toBeEnabled();
  await confirm.click();
}

for (const kind of ["journal", "conference", "patent", "book", "chapter"] as const) {
  test(`${kind}: deactivate/reactivate and confirmed permanent delete preserve linked masters`, async ({ page, request }) => {
    await verifyIsolatedStorage(request);
    const suffix = `${kind}-${Date.now()}`;
    const { faculty, student } = await createPeople(request, suffix);
    const record = await createRecord(request, kind, suffix, faculty, student);
    try {
      await openDetail(page, record);
      await expect(page.getByRole("button", { name: "Deactivate", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Delete", exact: true })).toBeVisible();

      await deleteThroughDialog(page, record, true);
      expect((await request.get(record.api)).ok()).toBeTruthy();

      await page.getByRole("button", { name: "Delete", exact: true }).click();
      const openDialog = page.getByRole("dialog");
      await expect(openDialog).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(openDialog).toHaveCount(0);

      await acceptDeactivate(page);
      await expect.poll(async () => (await request.get(record.api)).json()).toMatchObject({ is_active: false });
      await openDetail(page, record);
      await expect(page.getByRole("button", { name: "Reactivate", exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Reactivate", exact: true }).click();
      await expect.poll(async () => (await request.get(record.api)).json()).toMatchObject({ is_active: true });

      await acceptDeactivate(page);
      await openDetail(page, record);
      await expect(page.getByRole("button", { name: "Delete", exact: true })).toBeVisible();
      await deleteThroughDialog(page, record);
      await expect.poll(async () => (await request.get(record.api)).status()).toBe(404);
      const masters = await (await request.get("/api/masters")).json();
      expect(masters.faculty.some((person: { id: number }) => person.id === faculty.id)).toBeTruthy();
      expect(masters.students.some((person: { id: number }) => person.id === student.id)).toBeTruthy();
    } finally {
      await request.delete(`${record.api}/permanent`);
      await request.delete(`/api/faculty/${faculty.id}`);
      await request.delete(`/api/students/${student.id}`);
    }
  });
}

test("Faculty Master deletion is blocked through the Master UI while a linked record exists", async ({ page, request }) => {
  await verifyIsolatedStorage(request);
  const suffix = `master-${Date.now()}`;
  const { faculty, student } = await createPeople(request, suffix);
  const record = await createRecord(request, "journal", suffix, faculty, student);
  try {
    await page.goto("/masters");
    const row = page.getByRole("row").filter({ hasText: faculty.employee_id });
    await row.getByRole("button", { name: "Delete", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Delete Faculty Member?" });
    await dialog.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(dialog.getByRole("alert")).toContainText("publication author associations");
    expect((await request.get(record.api)).ok()).toBeTruthy();
  } finally {
    await request.delete(`${record.api}/permanent`);
    await request.delete(`/api/faculty/${faculty.id}`);
    await request.delete(`/api/students/${student.id}`);
  }
});

test("publication permanent deletion cleans only its isolated evidence files", async ({ page, request }) => {
  await verifyIsolatedStorage(request);
  const suffix = `evidence-${Date.now()}`;
  const { faculty, student } = await createPeople(request, suffix);
  const target = await createRecord(request, "journal", `${suffix}-target`, faculty, student);
  const unrelated = await createRecord(request, "conference", `${suffix}-other`, faculty, student);
  try {
    for (const record of [target, unrelated]) {
      const upload = await request.post(`${record.api}/evidence`, { multipart: { evidence_type: "PUBLISHED_PAPER", file: { name: `${record.id}.pdf`, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 E2E evidence") } } });
      expect(upload.status()).toBe(201);
    }
    const health = await (await request.get("/api/health")).json() as { evidence_path: string };
    const before = await evidenceFileCount(health.evidence_path);
    expect((await request.get(`${unrelated.api}/evidence`)).ok()).toBeTruthy();

    await openDetail(page, target);
    await deleteThroughDialog(page, target);
    await expect.poll(async () => (await request.get(target.api)).status()).toBe(404);
    const after = await evidenceFileCount(health.evidence_path);
    expect(after).toBe(before - 1);
    expect((await request.get(`${unrelated.api}/evidence`)).ok()).toBeTruthy();
  } finally {
    await request.delete(`${target.api}/permanent`);
    await request.delete(`${unrelated.api}/permanent`);
    await request.delete(`/api/faculty/${faculty.id}`);
    await request.delete(`/api/students/${student.id}`);
  }
});
