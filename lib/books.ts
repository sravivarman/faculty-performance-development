import {Evidence} from "./api";
import {Inventor} from "./patents";

export type Contributor = Omit<Inventor,"inventor_order"|"inventor_name"> & {contributor_order:number; contributor_name:string; role:"AUTHOR"|"EDITOR";source_metadata?:{author_name_from_source?:string;given_name_from_source?:string;family_name_from_source?:string;orcid_from_source?:string;affiliation_from_source?:string[];matching_status?:string;suggestions?:{id:number;name:string;person_type:string;reason:string}[]}};
export type Book = {
  id?:number; work_type:"BOOK"|"BOOK_CHAPTER"; title:string; parent_book_title:string|null; chapter_number:string|null;
  isbn:string|null; eisbn:string|null; doi:string|null; publisher:string; publication_date:string; edition:string|null;
  page_range:string|null; url:string|null; remarks:string|null; is_active:boolean; contributors:Contributor[];
  classification?:"INTERNATIONAL"|"NATIONAL"|"OTHER"|"UNKNOWN"|null;volume?:string|null;publication_year?:number|null;
  metadata_source?:"MANUAL"|"CROSSREF"|null;metadata_fetched_at?:string|null;raw_metadata_json?:Record<string,unknown>|null;
  evidence?:Evidence[]; evidence_count?:number; duplicate_acknowledged?:boolean;
  current_department_faculty_count?:number; current_department_student_count?:number;
  same_institution_other_department_count?:number; external_contributor_count?:number;
  change_log?:{id:number; action:string; changed_at:string}[];
};
export type BookMetadata = Partial<Book> & {source_type?:string;warnings?:string[]};
export function eligibleBookClaimant(c:Contributor,kind:Book["work_type"]){return c.person_type==="FACULTY"&&c.institution_scope==="CURRENT_DEPARTMENT"&&!!c.faculty_id&&(kind==="BOOK"||c.role==="AUTHOR");}
export function bookClaimantReady(book:Book){const claims=book.contributors.filter(c=>c.is_claiming_faculty);return claims.length===1&&eligibleBookClaimant(claims[0],book.work_type);}
export const bookMetrics = {total:"Total Works", books:"Books", chapters:"Book Chapters", with_students:"Student-involved", interdepartmental:"Works with Other VCE Departments", external_collaboration:"Works with External Collaboration", unique_faculty:"Unique Department Faculty Authors", unique_students:"Unique Department Student Authors"};
export const BOOK_EVIDENCE = ["COVER_PAGE","TITLE_PAGE","COPYRIGHT_PAGE","ISBN_PAGE","CHAPTER_FIRST_PAGE","TABLE_OF_CONTENTS","PUBLISHER_PROOF","FULL_CHAPTER","OTHER"];
export const blankContributor = (order:number):Contributor => ({contributor_order:order,contributor_name:"",role:"AUTHOR",person_type:"UNKNOWN",institution_scope:"UNKNOWN",faculty_id:null,student_id:null,department_name:null,institution_name:null,employee_or_roll_number:null,is_claiming_faculty:false});
export const blankBook = ():Book => ({work_type:"BOOK",title:"",parent_book_title:null,chapter_number:null,isbn:null,eisbn:null,doi:null,publisher:"",publication_date:"",edition:null,page_range:null,url:null,remarks:null,is_active:true,contributors:[]});
export type BookPersonKpi = {id:number;name:string;books_claimed?:number;books_authored:number;chapters_claimed?:number;chapters_authored:number;claimed?:number;authored:number;participated?:number;total_works?:number;roll_number?:string;faculty_collaborators?:{id:number;name:string}[]};
