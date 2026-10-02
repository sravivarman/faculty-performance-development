from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class AcademicYear(Base, Timestamps):
    __tablename__ = "academic_years"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    __table_args__ = (CheckConstraint("end_date >= start_date"),)


class Faculty(Base, Timestamps):
    __tablename__ = "faculty"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    designation: Mapped[str | None] = mapped_column(String(250))
    orcid: Mapped[str | None] = mapped_column(String(80), unique=True)
    scopus_author_id: Mapped[str | None] = mapped_column(String(80))
    name_variants: Mapped[list] = mapped_column(JSON, default=list)
    name_variant_strengths: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Student(Base, Timestamps):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    roll_number: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    batch: Mapped[str | None] = mapped_column(String(80))
    program: Mapped[str | None] = mapped_column(String(150))
    year_of_study: Mapped[int | None] = mapped_column(Integer)
    name_variants: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Publication(Base, Timestamps):
    __tablename__ = "publications"
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"), index=True)
    doi: Mapped[str | None] = mapped_column(String(1000, collation="NOCASE"), unique=True)
    title: Mapped[str] = mapped_column(Text)
    publication_type: Mapped[str] = mapped_column(String(20))
    journal_conference_name: Mapped[str | None] = mapped_column(Text)
    conference_name: Mapped[str | None] = mapped_column(Text)
    proceedings_title: Mapped[str | None] = mapped_column(Text)
    conference_start_date: Mapped[date | None] = mapped_column(Date)
    conference_end_date: Mapped[date | None] = mapped_column(Date)
    conference_location: Mapped[str | None] = mapped_column(Text)
    conference_organizer: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date] = mapped_column(Date, index=True)
    online_publication_date: Mapped[date | None] = mapped_column(Date)
    print_publication_date: Mapped[date | None] = mapped_column(Date)
    volume: Mapped[str | None] = mapped_column(String(100))
    issue: Mapped[str | None] = mapped_column(String(100))
    pages_or_article_number: Mapped[str | None] = mapped_column(String(200))
    issn: Mapped[str | None] = mapped_column(String(250))
    eissn: Mapped[str | None] = mapped_column(String(250))
    isbn: Mapped[str | None] = mapped_column(String(250))
    url: Mapped[str | None] = mapped_column(Text)
    indexing: Mapped[list] = mapped_column(JSON, default=list)
    classification: Mapped[str] = mapped_column(String(20), default="UNKNOWN", server_default="UNKNOWN")
    impact_factor: Mapped[float | None]
    quartile: Mapped[str | None] = mapped_column(String(20))
    remarks: Mapped[str | None] = mapped_column(Text)
    metadata_source: Mapped[str] = mapped_column(String(30), default="MANUAL")
    source_type: Mapped[str] = mapped_column(String(30), default="MANUAL", server_default="MANUAL")
    raw_bibtex: Mapped[str | None] = mapped_column(Text)
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_metadata_json: Mapped[dict | None] = mapped_column(JSON)
    is_claimable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    authors: Mapped[list["PublicationAuthor"]] = relationship(cascade="all, delete-orphan", order_by="PublicationAuthor.author_order", lazy="selectin")
    evidence: Mapped[list["EvidenceFile"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    __table_args__ = (
        CheckConstraint("publication_type IN ('JOURNAL','CONFERENCE','OTHER')", name="publication_type_valid"),
        CheckConstraint("classification IN ('INTERNATIONAL','NATIONAL','OTHER','UNKNOWN')", name="publication_classification_valid"),
        CheckConstraint("doi IS NULL OR (doi COLLATE BINARY = lower(trim(doi)) AND doi LIKE '10.%/%')", name="normalized_doi"),
    )


class PublicationAuthor(Base, Timestamps):
    __tablename__ = "publication_authors"
    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    author_order: Mapped[int] = mapped_column(Integer)
    author_name_from_source: Mapped[str] = mapped_column(Text)
    given_name_from_source: Mapped[str | None] = mapped_column(Text)
    family_name_from_source: Mapped[str | None] = mapped_column(Text)
    orcid_from_source: Mapped[str | None] = mapped_column(String(100))
    affiliation_from_source: Mapped[list] = mapped_column(JSON, default=list)
    person_type: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    faculty_id: Mapped[int | None] = mapped_column(ForeignKey("faculty.id"), index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), index=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_claiming_faculty: Mapped[bool] = mapped_column(Boolean, default=False)
    is_corresponding_author: Mapped[bool] = mapped_column(Boolean, default=False)
    is_first_author: Mapped[bool] = mapped_column(Boolean, default=False)
    matching_status: Mapped[str] = mapped_column(String(30), default="UNMATCHED")
    matching_confidence: Mapped[float | None]
    __table_args__ = (
        UniqueConstraint("publication_id", "author_order"),
        UniqueConstraint("publication_id", "faculty_id"),
        UniqueConstraint("publication_id", "student_id"),
        CheckConstraint("author_order > 0"),
        CheckConstraint("(person_type = 'FACULTY' AND faculty_id IS NOT NULL AND student_id IS NULL AND is_internal = 1) OR (person_type = 'STUDENT' AND student_id IS NOT NULL AND faculty_id IS NULL AND is_internal = 1) OR (person_type IN ('EXTERNAL', 'UNKNOWN') AND faculty_id IS NULL AND student_id IS NULL AND is_internal = 0)", name="author_identity"),
        CheckConstraint("is_claiming_faculty = 0 OR (person_type = 'FACULTY' AND faculty_id IS NOT NULL AND is_internal = 1)", name="internal_faculty_claimant"),
        Index("uq_publication_claimant", "publication_id", unique=True, sqlite_where=text("is_claiming_faculty = 1")),
    )


class EvidenceFile(Base, Timestamps):
    __tablename__ = "evidence_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int | None] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    patent_id: Mapped[int | None] = mapped_column(ForeignKey("patents.id", ondelete="CASCADE"), index=True)
    book_record_id: Mapped[int | None] = mapped_column(ForeignKey("book_publications.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text, unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    evidence_type: Mapped[str] = mapped_column(String(80), default="PUBLICATION_PROOF")
    __table_args__ = (CheckConstraint("(publication_id IS NOT NULL AND patent_id IS NULL AND book_record_id IS NULL) OR (patent_id IS NOT NULL AND publication_id IS NULL AND book_record_id IS NULL) OR (book_record_id IS NOT NULL AND publication_id IS NULL AND patent_id IS NULL)", name="one_evidence_owner"),)


class ChangeLog(Base):
    __tablename__ = "change_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    action: Mapped[str] = mapped_column(String(80))
    changes: Mapped[dict] = mapped_column(JSON)


class Patent(Base, Timestamps):
    __tablename__ = "patents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    application_number: Mapped[str | None] = mapped_column(String(200))
    normalized_application_number: Mapped[str | None] = mapped_column(String(200, collation="NOCASE"), unique=True)
    patent_office: Mapped[str] = mapped_column(String(150))
    country: Mapped[str | None] = mapped_column(String(150))
    patent_type: Mapped[str | None] = mapped_column(String(150))
    filing_date: Mapped[date | None] = mapped_column(Date, index=True)
    publication_number: Mapped[str | None] = mapped_column(String(200))
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    grant_number: Mapped[str | None] = mapped_column(String(200))
    grant_date: Mapped[date | None] = mapped_column(Date, index=True)
    current_status: Mapped[str] = mapped_column(String(30), default="FILED")
    applicant_assignee: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    is_claimable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    inventors: Mapped[list["PatentInventor"]] = relationship(cascade="all, delete-orphan", order_by="PatentInventor.inventor_order", lazy="selectin")
    evidence: Mapped[list[EvidenceFile]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    status_history: Mapped[list["PatentStatusHistory"]] = relationship(cascade="all, delete-orphan", order_by="PatentStatusHistory.id", lazy="selectin")
    __table_args__ = (CheckConstraint("current_status IN ('FILED','PUBLISHED','GRANTED','REJECTED','WITHDRAWN','OTHER')", name="patent_status_valid"),
                      CheckConstraint("patent_type IS NULL OR patent_type IN ('UTILITY','DESIGN','COPYRIGHT')", name="patent_type_valid"))


class PatentInventor(Base, Timestamps):
    __tablename__ = "patent_inventors"
    id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patents.id", ondelete="CASCADE"), index=True)
    inventor_order: Mapped[int] = mapped_column(Integer)
    inventor_name: Mapped[str] = mapped_column(Text)
    person_type: Mapped[str] = mapped_column(String(30))
    institution_scope: Mapped[str] = mapped_column(String(50))
    faculty_id: Mapped[int | None] = mapped_column(ForeignKey("faculty.id"), index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), index=True)
    department_name: Mapped[str | None] = mapped_column(String(200))
    institution_name: Mapped[str | None] = mapped_column(String(250))
    employee_or_roll_number: Mapped[str | None] = mapped_column(String(100))
    is_claiming_faculty: Mapped[bool] = mapped_column(Boolean, default=False)
    # Scope flags are derived, avoiding three independently editable representations.
    @property
    def is_internal_institution(self):
        return self.institution_scope in ("CURRENT_DEPARTMENT", "SAME_INSTITUTION_OTHER_DEPARTMENT")

    @property
    def is_current_department(self):
        return self.institution_scope == "CURRENT_DEPARTMENT"

    __table_args__ = (
        UniqueConstraint("patent_id", "inventor_order"),
        UniqueConstraint("patent_id", "faculty_id"), UniqueConstraint("patent_id", "student_id"),
        CheckConstraint("inventor_order > 0"),
        CheckConstraint("person_type IN ('FACULTY','STUDENT','EXTERNAL_PERSON','UNKNOWN')"),
        CheckConstraint("institution_scope IN ('CURRENT_DEPARTMENT','SAME_INSTITUTION_OTHER_DEPARTMENT','EXTERNAL_INSTITUTION','UNKNOWN')"),
        CheckConstraint("(faculty_id IS NULL OR (person_type='FACULTY' AND institution_scope='CURRENT_DEPARTMENT' AND student_id IS NULL)) AND (student_id IS NULL OR (person_type='STUDENT' AND institution_scope='CURRENT_DEPARTMENT' AND faculty_id IS NULL))", name="patent_local_identity"),
        CheckConstraint("is_claiming_faculty=0 OR (person_type='FACULTY' AND institution_scope='CURRENT_DEPARTMENT' AND faculty_id IS NOT NULL)", name="patent_department_claimant"),
    )


class PatentStatusHistory(Base):
    __tablename__ = "patent_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patents.id", ondelete="CASCADE"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    note: Mapped[str | None] = mapped_column(Text)


class PatentChangeLog(Base):
    __tablename__ = "patent_change_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patents.id"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    action: Mapped[str] = mapped_column(String(80))
    changes: Mapped[dict] = mapped_column(JSON)


class BookPublication(Base, Timestamps):
    __tablename__ = "book_publications"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(String(20))
    volume: Mapped[str | None] = mapped_column(String(100))
    publication_year: Mapped[int | None] = mapped_column(Integer)
    metadata_source: Mapped[str | None] = mapped_column(String(30))
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_metadata_json: Mapped[dict | None] = mapped_column(JSON)
    parent_book_title: Mapped[str | None] = mapped_column(Text)
    chapter_number: Mapped[str | None] = mapped_column(String(100))
    isbn: Mapped[str | None] = mapped_column(String(100))
    eisbn: Mapped[str | None] = mapped_column(String(100))
    normalized_isbn: Mapped[str | None] = mapped_column(String(13), index=True)
    normalized_eisbn: Mapped[str | None] = mapped_column(String(13), index=True)
    doi: Mapped[str | None] = mapped_column(String(1000, collation="NOCASE"), unique=True)
    publisher: Mapped[str] = mapped_column(Text)
    publication_date: Mapped[date] = mapped_column(Date, index=True)
    edition: Mapped[str | None] = mapped_column(String(100))
    page_range: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    contributors: Mapped[list["BookContributor"]] = relationship(cascade="all, delete-orphan", order_by="BookContributor.contributor_order", lazy="selectin")
    evidence: Mapped[list[EvidenceFile]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    __table_args__ = (
        CheckConstraint("work_type IN ('BOOK','BOOK_CHAPTER')", name="book_work_type"),
        CheckConstraint("work_type != 'BOOK_CHAPTER' OR (parent_book_title IS NOT NULL AND page_range IS NOT NULL)", name="chapter_details"),
        CheckConstraint("doi IS NULL OR (doi COLLATE BINARY = lower(trim(doi)) AND doi LIKE '10.%/%')", name="book_normalized_doi"),
    )


class BookContributor(Base, Timestamps):
    __tablename__ = "book_contributors"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_record_id: Mapped[int] = mapped_column(ForeignKey("book_publications.id", ondelete="CASCADE"), index=True)
    contributor_order: Mapped[int] = mapped_column(Integer)
    contributor_name: Mapped[str] = mapped_column(Text)
    source_metadata: Mapped[dict | None] = mapped_column(JSON)
    role: Mapped[str] = mapped_column(String(20))
    person_type: Mapped[str] = mapped_column(String(30))
    institution_scope: Mapped[str] = mapped_column(String(50))
    faculty_id: Mapped[int | None] = mapped_column(ForeignKey("faculty.id"), index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), index=True)
    institution_name: Mapped[str | None] = mapped_column(String(250))
    department_name: Mapped[str | None] = mapped_column(String(200))
    employee_or_roll_number: Mapped[str | None] = mapped_column(String(100))
    is_claiming_faculty: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def is_current_department(self):
        return self.institution_scope == "CURRENT_DEPARTMENT"

    @property
    def is_internal_institution(self):
        return self.institution_scope in ("CURRENT_DEPARTMENT", "SAME_INSTITUTION_OTHER_DEPARTMENT")

    __table_args__ = (
        UniqueConstraint("book_record_id", "contributor_order"),
        UniqueConstraint("book_record_id", "faculty_id", "role"),
        UniqueConstraint("book_record_id", "student_id", "role"),
        CheckConstraint("contributor_order > 0"),
        CheckConstraint("role IN ('AUTHOR','EDITOR')"),
        CheckConstraint("person_type IN ('FACULTY','STUDENT','EXTERNAL_PERSON','UNKNOWN')"),
        CheckConstraint("institution_scope IN ('CURRENT_DEPARTMENT','SAME_INSTITUTION_OTHER_DEPARTMENT','EXTERNAL_INSTITUTION','UNKNOWN')"),
        CheckConstraint("(faculty_id IS NULL OR (person_type='FACULTY' AND institution_scope='CURRENT_DEPARTMENT' AND student_id IS NULL)) AND (student_id IS NULL OR (person_type='STUDENT' AND institution_scope='CURRENT_DEPARTMENT' AND faculty_id IS NULL))", name="book_local_identity"),
        CheckConstraint("is_claiming_faculty=0 OR (person_type='FACULTY' AND institution_scope='CURRENT_DEPARTMENT' AND faculty_id IS NOT NULL)", name="book_department_claimant"),
        Index("uq_book_claimant", "book_record_id", unique=True, sqlite_where=text("is_claiming_faculty=1")),
    )


class BookChangeLog(Base):
    __tablename__ = "book_change_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_record_id: Mapped[int] = mapped_column(ForeignKey("book_publications.id"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    action: Mapped[str] = mapped_column(String(80))
    changes: Mapped[dict] = mapped_column(JSON)
