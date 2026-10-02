export type PersonType = "FACULTY" | "STUDENT" | "EXTERNAL" | "UNKNOWN";
export type Person = {id: number; name: string; is_active: boolean; name_variants: string[]; weak_name_variants?: string[]; name_variant_strengths?: Record<string,"STRONG"|"WEAK">; employee_id?: string; designation?: string; orcid?: string; scopus_author_id?: string; roll_number?: string; batch?: string; program?: string; year_of_study?: number};
export type Year = {id: number; name: string; start_date: string; end_date: string};
export type Masters = {faculty: Person[]; students: Person[]; academic_years: Year[]};
export type Author = {
  author_order: number; author_name_from_source: string; given_name_from_source?: string | null; family_name_from_source?: string | null;
  orcid_from_source?: string | null; affiliation_from_source: string[]; person_type: PersonType; faculty_id: number | null; student_id: number | null;
  is_internal: boolean; is_claiming_faculty: boolean; is_corresponding_author: boolean; is_first_author: boolean;
  matching_status: string; matching_confidence?: number | null; person_name?: string | null;
  suggestions?: {person_type: PersonType; id: number; name: string; confidence: number; reason: string}[];
};
export type Evidence = {id: number; original_filename: string; evidence_type: string; size_bytes: number};
export type Publication = {
  id?: number; academic_year_id?: number; doi: string | null; title: string; publication_type: string;
  publication_date: string; online_publication_date?: string | null; print_publication_date?: string | null;
  journal_conference_name?: string | null; publisher?: string | null; volume?: string | null; issue?: string | null;
  conference_name?: string | null; proceedings_title?: string | null; conference_start_date?: string | null; conference_end_date?: string | null;
  conference_location?: string | null; conference_organizer?: string | null;
  pages_or_article_number?: string | null; issn?: string | null; eissn?: string | null; isbn?: string | null;
  url?: string | null; indexing: string[]; impact_factor?: number | null; quartile?: string | null; remarks?: string | null;
  classification?: string;
  source_type?: string; raw_bibtex?: string | null;
  metadata_source: string; metadata_fetched_at?: string | null; raw_metadata_json?: Record<string, unknown> | null;
  is_claimable: boolean; is_active: boolean; authors: Author[]; evidence?: Evidence[]; evidence_count?: number;
  classifications?: string[]; created_at?: string; updated_at?: string; duplicate_acknowledged?: boolean;
  change_log?: {id: number; action: string; changed_at: string}[];
};
export const INDEXING = ["SCOPUS", "WEB_OF_SCIENCE", "SCI", "SCIE", "ESCI", "UGC_CARE", "OTHER", "NONE", "UNKNOWN"];
export const label = (value: string) => value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
export class ApiError extends Error {
  constructor(message: string, public detail?: {publication_id?: number; patent_id?:number; book_id?:number; possible_duplicate_ids?: number[]}, public status?:number) {super(message);}
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {...options, headers: {...(options?.body instanceof FormData ? {} : {"Content-Type": "application/json"}), ...options?.headers}});
  if (!response.ok) {
    const body = await response.json().catch(() => ({detail: "Request failed"}));
    const detail = body.detail;
    throw new ApiError(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(d => `${d.loc?.slice(1).join(".")}: ${d.msg}`).join("; ") : detail?.message || "Request failed", detail, response.status);
  }
  return response.json();
}
export const blankAuthor = (order: number): Author => ({author_order: order, author_name_from_source: "", affiliation_from_source: [], person_type: "UNKNOWN", faculty_id: null, student_id: null, is_internal: false, is_claiming_faculty: false, is_corresponding_author: false, is_first_author: order === 1, matching_status: "UNMATCHED"});
export const blankPublication = (): Publication => ({doi: "", title: "", publication_type: "JOURNAL", publication_date: "", indexing: [], metadata_source: "MANUAL", is_claimable: true, is_active: true, authors: []});
