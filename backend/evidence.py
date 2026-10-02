"""Shared local evidence infrastructure for publication and patent records."""
import hashlib
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import db as database
from .db import get_db
from .models import BookChangeLog, BookPublication, ChangeLog, EvidenceFile, Patent, PatentChangeLog, Publication, now
from .services import columns

router = APIRouter()
DB = Annotated[Session,Depends(get_db)]
Entity = Literal["publications","patents","books"]
OWNERS = {"publications": "publication_id", "patents": "patent_id", "books": "book_record_id"}
BOOK_EVIDENCE_TYPES = {"COVER_PAGE", "TITLE_PAGE", "COPYRIGHT_PAGE", "ISBN_PAGE", "CHAPTER_FIRST_PAGE", "TABLE_OF_CONTENTS", "PUBLISHER_PROOF", "FULL_CHAPTER", "OTHER"}


def evidence_parent(db,entity,identity):
    model = {"publications": Publication, "patents": Patent, "books": BookPublication}[entity]
    parent = db.get(model,identity)
    if not parent:
        raise HTTPException(404,"Record not found")
    return parent


def log_evidence(db,entity,identity,action,changes):
    model = {"publications": ChangeLog, "patents": PatentChangeLog, "books": BookChangeLog}[entity]
    log = model(**{OWNERS[entity]: identity}, action=action, changes=changes)
    db.add(log)


@router.post("/{entity}/{identity}/evidence",status_code=201)
def upload_evidence(entity:Entity,identity:int,db:DB,file:UploadFile=File(...),evidence_type:str=Form("OTHER")):
    parent = evidence_parent(db,entity,identity)
    categories = {"PUBLISHED_PAPER","FIRST_PAGE","INDEXING_PROOF","ACCEPTANCE_LETTER","PUBLICATION_PROOF","CONFERENCE_PAPER","PROCEEDINGS_FIRST_PAGE","CERTIFICATE","CONFERENCE_PROGRAM","OTHER"} if entity == "publications" else {"FILING_PROOF","PUBLICATION_PROOF","GRANT_PROOF","OTHER"}
    if entity == "books":
        categories = BOOK_EVIDENCE_TYPES
    if evidence_type not in categories:
        raise HTTPException(422,"Unknown evidence category for this record")
    filename = Path((file.filename or "evidence").replace("\\","/")).name
    suffix = Path(filename).suffix.lower()
    media = {".pdf":"application/pdf",".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if suffix not in media:
        raise HTTPException(422,"Upload a PDF, PNG, JPG or DOCX file")
    reporting_date = parent.publication_date if entity in ("publications", "books") else parent.filing_date
    year = reporting_date.year - (reporting_date.month < 7) if reporting_date else None
    folder = f"{year}-{str(year+1)[-2:]}" if year else "UNDATED"
    kind = "PAPER" if entity == "publications" else "PATENT"
    if entity == "books":
        kind = parent.work_type
    relative = Path(folder)/kind/str(identity)/f"{uuid.uuid4()}{suffix}"
    target = database.EVIDENCE_ROOT/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    size,digest = 0,hashlib.sha256()
    try:
        with target.open("xb") as output:
            while chunk := file.file.read(1024*1024):
                size += len(chunk)
                if size > 25*1024*1024:
                    raise HTTPException(413,"Evidence must be 25 MB or smaller")
                output.write(chunk);digest.update(chunk)
        if not size:
            raise HTTPException(422,"Evidence file is empty")
        owner = {OWNERS[entity]:identity}
        evidence = EvidenceFile(**owner,original_filename=filename,storage_path=relative.as_posix(),content_type=media[suffix],size_bytes=size,sha256=digest.hexdigest(),evidence_type=evidence_type)
        db.add(evidence);parent.updated_at = now()
        log_evidence(db,entity,identity,"EVIDENCE_ADD",{"filename":filename,"evidence_type":evidence_type})
        db.commit()
        return {k:v for k,v in columns(evidence).items() if k != "storage_path"}
    except Exception:
        db.rollback();target.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


def find_evidence(db,entity,identity,evidence_id,require_file=True):
    item = db.get(EvidenceFile,evidence_id)
    owner = OWNERS[entity]
    if not item or getattr(item,owner) != identity:
        raise HTTPException(404,"Evidence not found")
    root = database.EVIDENCE_ROOT.resolve()
    target = (root/item.storage_path).resolve()
    if not target.is_relative_to(root) or (require_file and not target.is_file()):
        raise HTTPException(404,"Evidence file is missing from local storage")
    return item,target


@router.get("/{entity}/{identity}/evidence/{evidence_id}")
def download_evidence(entity:Entity,identity:int,evidence_id:int,db:DB,download:bool=False):
    item,target = find_evidence(db,entity,identity,evidence_id)
    return FileResponse(target,media_type=item.content_type,filename=item.original_filename,
                        content_disposition_type="attachment" if download or target.suffix == ".docx" else "inline",
                        headers={"X-Content-Type-Options":"nosniff","Content-Security-Policy":"sandbox"})


@router.delete("/{entity}/{identity}/evidence/{evidence_id}")
def remove_evidence(entity:Entity,identity:int,evidence_id:int,db:DB):
    item,target = find_evidence(db,entity,identity,evidence_id,require_file=False)
    log_evidence(db,entity,identity,"EVIDENCE_REMOVE",{"filename":item.original_filename})
    db.delete(item);evidence_parent(db,entity,identity).updated_at = now()
    db.commit();target.unlink(missing_ok=True)
    return {"removed":evidence_id}
