"""Conservative name normalization; never expands initials or corrects spelling."""
import re
import unicodedata


def normalize_person_name(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    tokens = value.split()
    while tokens and tokens[0] in {"dr", "mr", "ms"}:
        tokens.pop(0)
    # H.S., H S and HS share a key; standalone initials stay intact.
    result, initials = [], []
    for token in tokens + [""]:
        if len(token) == 1 and token.isalpha():
            initials.append(token)
        else:
            if initials:
                result.append("".join(initials)); initials = []
            if token:
                result.append(token)
    return " ".join(result)


def prepare_variants(variants, strengths=None):
    """One stored spelling per normalized alias, with explicit match strengths."""
    configured = {}
    for value, strength in (strengths or {}).items():
        key = normalize_person_name(value)
        if strength not in {"STRONG", "WEAK"}:
            raise ValueError("Name variant strengths must be STRONG or WEAK")
        if key in configured and configured[key] != strength:
            raise ValueError("Conflicting strengths for the same normalized name variant")
        configured[key] = strength
    retained = {}
    for value in variants:
        key = normalize_person_name(value)
        if not key:
            raise ValueError("Name variants must contain a name")
        retained.setdefault(key, value.strip())
    if set(configured) - set(retained):
        raise ValueError("Strengths may only be set for approved name variants")
    return list(retained.values()), {key: configured.get(key, "STRONG") for key in retained}
