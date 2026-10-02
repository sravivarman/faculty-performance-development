import {INDEXING, Publication} from "./api";

export const isSaveable = (status:string) => status === "READY" || status === "READY_WITH_WARNINGS";

export function authorWarnings(publication:Publication) {
  const unknown=publication.authors.filter(a=>a.person_type === "UNKNOWN");
  const internal=unknown.filter(a=>a.affiliation_from_source.some(value=>/\bvardhaman\b|\bvardhman\b/i.test(value)));
  return [
    ...(unknown.length?[`${unknown.length} co-author(s) remain unclassified.`]:[]),
    ...(internal.length?[`UNRESOLVED_INTERNAL_AUTHOR: ${internal.length} Vardhaman-affiliated author(s) remain unclassified.`]:[]),
  ];
}

function validDate(value:string) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date=new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0,10)===value;
}

export function doiReadiness(publication:Publication,reviewed:boolean,duplicate=false,requireDoi=true) {
  if(publication.id) return "SAVED";
  if(duplicate) return "DUPLICATE";
  let doi=publication.doi || "";
  try {doi=decodeURIComponent(doi.trim().replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i,""));}
  catch {return "INVALID_DOI";}
  if((requireDoi || doi) && !/^10\.\d{4,9}\/[^\s]+$/.test(doi)) return "INVALID_DOI";
  const authors=publication.authors;
  if(!publication.title.trim() || !["JOURNAL","CONFERENCE"].includes(publication.publication_type) || !validDate(publication.publication_date)
    || (publication.impact_factor != null && (!Number.isFinite(publication.impact_factor) || publication.impact_factor<0))
    || (publication.quartile && !["Q1","Q2","Q3","Q4","UNKNOWN","NOT_APPLICABLE"].includes(publication.quartile))
    || publication.indexing.some(value=>!INDEXING.includes(value))
    || (publication.indexing.length>1 && publication.indexing.some(value=>["NONE","UNKNOWN"].includes(value)))
    || authors.some(a=>!a.author_name_from_source.trim() || (a.person_type === "FACULTY" && (!a.faculty_id || a.student_id || a.matching_status === "SUGGESTED"))
      || (a.person_type === "STUDENT" && (!a.student_id || a.faculty_id || a.matching_status === "SUGGESTED"))
      || (["UNKNOWN","EXTERNAL"].includes(a.person_type) && (a.faculty_id || a.student_id)))) return "INVALID";
  const claims=authors.filter(a=>a.is_claiming_faculty);
  if(!claims.length) return "NEEDS_CLAIMANT";
  if(claims.length!==1 || !publication.is_claimable || claims[0].person_type!=="FACULTY" || !claims[0].faculty_id) return "INVALID";
  if(!reviewed) return "AUTHOR_REVIEW"; // Review confirmation is still mandatory.
  return authorWarnings(publication).length ? "READY_WITH_WARNINGS" : "READY";
}

export const CLASSIFICATIONS=["INTERNATIONAL","NATIONAL","OTHER","UNKNOWN"];
export const QUARTILES=["Q1","Q2","Q3","Q4","NOT_APPLICABLE","UNKNOWN"];
export function prepareQueuePublication(publication:Publication):Publication {
  const faculty=publication.authors.filter(a=>a.person_type==="FACULTY" && a.faculty_id && a.matching_status!=="SUGGESTED");
  return {...publication,classification:publication.classification || "UNKNOWN",quartile:publication.quartile || "UNKNOWN",
    authors:publication.authors.map(a=>({...a,is_claiming_faculty:faculty.length===1?a===faculty[0]:a.is_claiming_faculty}))};
}
export function queueWarnings(publication:Publication) {
  return [...authorWarnings(publication),...(!publication.journal_conference_name?["Venue not supplied."]:[]),
    ...(publication.impact_factor==null?["Impact factor not supplied."]:[]),
    ...(!publication.quartile || publication.quartile==="UNKNOWN"?["Quartile unknown."]:[])];
}
export function queueReadiness(publication:Publication,duplicate=false) {
  if(publication.id) return "SAVED";
  if(duplicate) return "DUPLICATE";
  if(!publication.title.trim() || !publication.publication_date || !["JOURNAL","CONFERENCE"].includes(publication.publication_type)) return "NEEDS_METADATA";
  if(!CLASSIFICATIONS.includes(publication.classification || "UNKNOWN")) return "INVALID";
  const status=doiReadiness(publication,true,false,publication.source_type==="DOI");
  if(status==="INVALID_DOI") return "INVALID";
  return isSaveable(status) && queueWarnings(publication).length ? "READY_WITH_WARNINGS" : status;
}
