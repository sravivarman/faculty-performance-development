import {Author, Publication} from "@/lib/api";

export const REVIEW_PACKAGE_SCHEMA = "vce.bulk-publication-review";
export const REVIEW_PACKAGE_VERSION = 1;
export const REVIEW_LOCAL_STORAGE_PREFIX = "vce.bulk-publication-review:";

export type ReviewStep = "identity" | "duplicate" | "classification" | "metadata" | "date" | "contributors" | "claimant";
export type ReviewStepState = "NOT_STARTED" | "CONFIRMED" | "REQUIRES_REVIEW" | "BLOCKED";
export type ReviewStatus = "NOT_REVIEWED" | "IN_REVIEW" | "BLOCKED" | "READY_FOR_FINAL_VALIDATION" | "VALIDATED_FOR_STAGE_2B";
export type ContributorDecision = {kind: "UNRESOLVED" | "EXTERNAL" | "FACULTY" | "STUDENT"; person_id?: number; display_name?: string};

export type ReviewRecord = {
  record_id: string;
  entry_number: number;
  source_doi?: string | null;
  source_eid?: string | null;
  source_title: string;
  duplicate_status: string;
  source_identity: string;
  suggested_module?: string;
  original: Partial<Publication>;
  draft: Partial<Publication>;
  contributors: Record<string, ContributorDecision>;
  claiming_faculty_id?: number;
  confirmed_steps: Partial<Record<ReviewStep, ReviewStepState>>;
  manual_date?: {date: string; evidence: string; date_type: string; explanation?: string};
  date_evidence?: unknown;
  review_status: ReviewStatus;
  warnings: string[];
};

export type ReviewSession = {
  schema: typeof REVIEW_PACKAGE_SCHEMA;
  version: typeof REVIEW_PACKAGE_VERSION;
  session_id: string;
  created_at: string;
  updated_at: string;
  analysis_version: "stage-1d";
  readiness_policy_version: "stage-2a-1";
  bibtex: {name: string; fingerprint: string};
  scopus?: {name: string; fingerprint: string};
  records: ReviewRecord[];
};

export type ReviewPackage = {package: ReviewSession; integrity: {algorithm: "SHA-256"; digest: string}};
export type ReviewPackageErrorCode = "PACKAGE_INTEGRITY_FAILED" | "UNSUPPORTED_SCHEMA_VERSION" | "INVALID_PACKAGE_STRUCTURE" | "SOURCE_FINGERPRINT_MISMATCH" | "DUPLICATE_RECORD_IDENTIFIER" | "RECORD_IDENTITY_MISMATCH";

export class ReviewPackageError extends Error {
  constructor(public readonly code: ReviewPackageErrorCode, message: string) { super(message); this.name = "ReviewPackageError"; }
}

const encoder = new TextEncoder();

/**
 * Matches JSON's own treatment of optional values before applying deterministic
 * object-key ordering. In particular, JSON removes undefined object members
 * and converts undefined array members to null. The old implementation hashed
 * the string "undefined" but exported JSON omitted that member, making a
 * freshly exported package fail verification after JSON.parse.
 */
function canonicalize(value: unknown, inArray = false): unknown {
  if (value === undefined || typeof value === "function" || typeof value === "symbol") return inArray ? null : undefined;
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "bigint") throw new TypeError("Review packages cannot contain bigint values.");
  if (value instanceof Date) return value.toJSON();
  if (Array.isArray(value)) return value.map(item => canonicalize(item, true));
  if (typeof value === "object") {
    const object = value as Record<string, unknown>;
    const normalized: Record<string, unknown> = {};
    for (const key of Object.keys(object).sort()) {
      const nested = canonicalize(object[key]);
      if (nested !== undefined) normalized[key] = nested;
    }
    return normalized;
  }
  return value;
}

export function stableStringify(value: unknown): string {
  const normalized = canonicalize(value);
  if (normalized === undefined) throw new TypeError("A review package cannot have an undefined root value.");
  return JSON.stringify(normalized);
}

export async function sha256(value: string | ArrayBuffer): Promise<string> {
  const input = typeof value === "string" ? encoder.encode(value) : value;
  const digest = await crypto.subtle.digest("SHA-256", input);
  return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
}

export async function fingerprintFile(file: File): Promise<string> {
  return sha256(await file.arrayBuffer());
}

export function recordIdentity(sourceFingerprint: string, entryNumber: number, doi?: string | null, eid?: string | null) {
  // Entry position is deliberately included because citation keys and DOIs can repeat.
  return `${sourceFingerprint}:${entryNumber}:${(doi || "").trim().toLowerCase()}:${eid || ""}`;
}

export function reviewStorageKey(fingerprint: string) {
  return `${REVIEW_LOCAL_STORAGE_PREFIX}${fingerprint}`;
}

export function isSafeJson(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const walk = (item: unknown): boolean => {
    if (item === null || typeof item !== "object") return true;
    if (Array.isArray(item)) return item.every(walk);
    return Object.entries(item as Record<string, unknown>).every(([key, nested]) => !["__proto__", "prototype", "constructor"].includes(key) && walk(nested));
  };
  return walk(value);
}

export async function makeReviewPackage(session: ReviewSession): Promise<ReviewPackage> {
  const canonical = stableStringify(session);
  return {package: session, integrity: {algorithm: "SHA-256", digest: await sha256(canonical)}};
}

export async function validateReviewPackage(value: unknown, expectedSources?: {bibtex: string; scopus?: string}): Promise<ReviewSession> {
  if (!isSafeJson(value)) throw new ReviewPackageError("INVALID_PACKAGE_STRUCTURE", "The review package is not a safe JSON object.");
  const packet = value as Partial<ReviewPackage>;
  if (!packet.package || !packet.integrity || packet.package.schema !== REVIEW_PACKAGE_SCHEMA) {
    throw new ReviewPackageError("INVALID_PACKAGE_STRUCTURE", "This is not a supported Stage 2A review package.");
  }
  if (packet.package.version !== REVIEW_PACKAGE_VERSION) {
    throw new ReviewPackageError("UNSUPPORTED_SCHEMA_VERSION", "This review package uses an unsupported schema version.");
  }
  if (packet.integrity.algorithm !== "SHA-256" || typeof packet.integrity.digest !== "string" ||
      packet.integrity.digest !== await sha256(stableStringify(packet.package))) {
    throw new ReviewPackageError("PACKAGE_INTEGRITY_FAILED", "The review package integrity check failed.");
  }
  const session = packet.package as ReviewSession;
  if (!session.bibtex?.fingerprint || !Array.isArray(session.records) || !session.records.every(record => Boolean(record) && typeof record === "object" && typeof record.record_id === "string" && Number.isInteger(record.entry_number))) {
    throw new ReviewPackageError("INVALID_PACKAGE_STRUCTURE", "The review package has an invalid record structure.");
  }
  if (new Set(session.records.map(record => record.record_id)).size !== session.records.length) {
    throw new ReviewPackageError("DUPLICATE_RECORD_IDENTIFIER", "The review package contains duplicate source record identifiers.");
  }
  if (!session.records.every(record => record.record_id === recordIdentity(session.bibtex.fingerprint, record.entry_number, record.source_doi, record.source_eid))) {
    throw new ReviewPackageError("RECORD_IDENTITY_MISMATCH", "A review record does not match its protected source identity.");
  }
  if (expectedSources?.bibtex && session.bibtex?.fingerprint !== expectedSources.bibtex) {
    throw new ReviewPackageError("SOURCE_FINGERPRINT_MISMATCH", "This review package belongs to different BibTeX source data. Reanalyze the original source before restoring it.");
  }
  if ((expectedSources?.scopus || session.scopus?.fingerprint) && expectedSources?.scopus !== session.scopus?.fingerprint) {
    throw new ReviewPackageError("SOURCE_FINGERPRINT_MISMATCH", "This review package belongs to different Scopus source data. Reanalyze the original source before restoring it.");
  }
  return session;
}

export function downloadReviewPackage(packet: ReviewPackage) {
  const blob = new Blob([JSON.stringify(packet, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = `publication-review-${packet.package.session_id}.json`;
  link.click(); URL.revokeObjectURL(url);
}
