import re
import unicodedata
from difflib import SequenceMatcher

from .doi import normalize_orcid
from .name_variants import normalize_person_name

MATCH_PRIORITY = {"ORCID": 0, "NAME": 1, "NAME_VARIANT": 2, "WEAK_VARIANT": 3, "FUZZY": 4}


def exact_match_reason(name, person, orcid=None):
    person_orcid = getattr(person, "orcid", None)
    if orcid and person_orcid == orcid:
        return "ORCID", 1.0
    if orcid and person_orcid and person_orcid != orcid:
        return None
    if name and name == normalize_person_name(person.name):
        return "NAME", .99
    if name and name in {normalize_person_name(v) for v in person.name_variants}:
        strengths = getattr(person, "name_variant_strengths", None) or {}
        return ("WEAK_VARIANT", .88) if strengths.get(name) == "WEAK" else ("NAME_VARIANT", .98)
    return None


def reconcile_faculty_name(value, faculty, orcid=None):
    """Exact approved keys only; ambiguous and weak matches always need review."""
    name = normalize_person_name(value)
    candidates = []
    for person in faculty:
        if person.is_active:
            match = exact_match_reason(name, person, orcid)
            if match:
                candidates.append((person, match[0]))
    candidates.sort(key=lambda c: (MATCH_PRIORITY[c[1]], c[0].employee_id))
    orcid_matches = [c for c in candidates if c[1] == "ORCID"]
    if orcid_matches:
        candidates = orcid_matches
    if len(candidates) != 1:
        return {"normalized_value": name, "matched_faculty": None, "employee_id": None,
                "match_source": "AMBIGUOUS" if candidates else "UNMATCHED", "requires_review": True,
                "candidates": [{"employee_id": p.employee_id, "name": p.name, "source": r} for p, r in candidates]}
    person, reason = candidates[0]
    return {"normalized_value": name, "matched_faculty": person.name, "employee_id": person.employee_id,
            "match_source": {"NAME": "CANONICAL", "NAME_VARIANT": "STRONG_VARIANT"}.get(reason, reason),
            "requires_review": reason == "WEAK_VARIANT", "candidates": []}


def normalized_name(value):
    value = unicodedata.normalize("NFKD", value or "").casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", "".join(c for c in value if not unicodedata.combining(c))).split())


def match_author(author, faculty, students):
    people = [("FACULTY", p) for p in faculty if p.is_active] + [("STUDENT", p) for p in students if p.is_active]
    try:
        orcid = normalize_orcid(author.get("orcid_from_source"))
    except ValueError:
        orcid = None
    name = normalize_person_name(author["author_name_from_source"])
    candidates = []
    for kind, person in people:
        names = [normalize_person_name(person.name)] + [normalize_person_name(v) for v in person.name_variants]
        person_orcid = getattr(person, "orcid", None)
        if orcid and kind == "FACULTY" and person_orcid and person_orcid != orcid:
            continue
        exact = exact_match_reason(name, person, orcid if kind == "FACULTY" else None)
        if exact:
            reason, score = exact
        else:
            score = max((SequenceMatcher(None, name, n).ratio() for n in names if n), default=0) * .94
            reason = "FUZZY"
        if score >= .80:
            candidates.append({"person_type": kind, "id": person.id, "name": person.name, "confidence": round(score, 3), "reason": reason})
    candidates.sort(key=lambda c: (MATCH_PRIORITY[c["reason"]], -c["confidence"]))
    result = {**author, "suggestions": candidates[:5]}
    if candidates:
        top = candidates[0]
        exact_candidates = [c for c in candidates if c["reason"] != "FUZZY"]
        certain = top["reason"] not in {"FUZZY", "WEAK_VARIANT"} and (
            len(exact_candidates) == 1 or (top["reason"] == "ORCID" and sum(c["reason"] == "ORCID" for c in candidates) == 1))
        result["matching_confidence"] = top["confidence"]
        result["matching_status"] = "EXACT" if certain else "SUGGESTED"
        if certain:
            result.update(person_type=top["person_type"], is_internal=True)
            result["faculty_id" if top["person_type"] == "FACULTY" else "student_id"] = top["id"]
    return result
