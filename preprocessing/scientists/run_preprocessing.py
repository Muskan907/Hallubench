
import json
import re
import hashlib
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data/raw/scientists"
OUT = ROOT / "data/processed/scientists"

OUT.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def read_jsonl(path):
    records = []

    if not path.exists():
        print(f"[WARNING] Missing: {path.name}")
        return records

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[WARNING] Invalid JSON: {path.name}, line {line_number}")

    return records


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def normalize_name(name):
    if not name:
        return ""

    name = str(name).lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    return " ".join(name.split())


def normalize_orcid(orcid):
    if not orcid:
        return None

    return str(orcid).rstrip("/").split("/")[-1]


def birth_year(value):
    if not value:
        return None

    match = re.search(r"\d{4}", str(value))
    return match.group(0) if match else None


def make_id(prefix, value):
    digest = hashlib.sha256(str(value).encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


def clean_list(values):
    if not isinstance(values, list):
        values = [values] if values else []

    return list(dict.fromkeys(
        str(v).strip() for v in values if v and str(v).strip()
    ))


# --------------------------------------------------
# LOAD RAW DATA
# --------------------------------------------------

print("\n========== SCIENTISTS PREPROCESSING ==========\n")

openalex = read_jsonl(RAW / "openalex_authors.jsonl")
wikidata = read_jsonl(RAW / "wikidata_scientists_enriched.jsonl")
nobel = read_jsonl(RAW / "nobel_laureates.jsonl")
orcid = read_jsonl(RAW / "orcid_records.jsonl")
crossref = read_jsonl(RAW / "crossref_publications.jsonl")

print("Raw records loaded:")
print("OpenAlex:", len(openalex))
print("Wikidata:", len(wikidata))
print("Nobel:", len(nobel))
print("ORCID:", len(orcid))
print("Crossref:", len(crossref))


# --------------------------------------------------
# NORMALIZE SCIENTIST RECORDS
# --------------------------------------------------

scientists = {}
source_mapping = []
name_index = defaultdict(list)


def create_scientist(source, source_id, name=None, orcid_id=None,
                     birth=None, death=None):

    normalized = normalize_name(name)
    orcid_id = normalize_orcid(orcid_id)

    # Exact ORCID is the strongest cross-source match.
    key = f"orcid:{orcid_id}" if orcid_id else None

    # Conservative fallback: exact normalized name AND birth year.
    # Do not merge on name alone.
    if not key and normalized and birth_year(birth):
        candidate_key = f"name:{normalized}:{birth_year(birth)}"

        if candidate_key in scientists:
            key = candidate_key

    if not key:
        key = f"{source}:{source_id}"

    if key not in scientists:
        scientists[key] = {
            "scientist_id": make_id("scientist", key),
            "name": name,
            "normalized_name": normalized or None,
            "orcid": orcid_id,
            "birth_date": birth,
            "birth_year": birth_year(birth),
            "death_date": death,
            "research_fields": [],
            "occupations": [],
            "institutions": [],
            "awards": [],
            "openalex_ids": [],
            "wikidata_ids": [],
            "nobel_ids": [],
            "sources": []
        }

    person = scientists[key]

    if not person["name"] and name:
        person["name"] = name
        person["normalized_name"] = normalized

    if not person["orcid"] and orcid_id:
        person["orcid"] = orcid_id

    if not person["birth_date"] and birth:
        person["birth_date"] = birth
        person["birth_year"] = birth_year(birth)

    if not person["death_date"] and death:
        person["death_date"] = death

    if source not in person["sources"]:
        person["sources"].append(source)

    source_mapping.append({
        "source": source,
        "source_id": str(source_id),
        "scientist_id": person["scientist_id"]
    })

    return person


# --------------------------------------------------
# OPENALEX
# --------------------------------------------------

for record in openalex:
    person = create_scientist(
        "OpenAlex",
        record.get("author_id"),
        record.get("name"),
        record.get("orcid")
    )

    if record.get("author_id"):
        person["openalex_ids"].append(record["author_id"])

    person["institutions"].extend([
        institution.get("name")
        for institution in record.get("institutions", [])
        if institution.get("name")
    ])

    person["openalex_stats"] = {
        "works_count": record.get("works_count"),
        "cited_by_count": record.get("cited_by_count"),
        "h_index": record.get("h_index"),
        "i10_index": record.get("i10_index")
    }


# --------------------------------------------------
# ORCID
# --------------------------------------------------

for record in orcid:
    raw = record.get("record") or {}
    person_data = raw.get("person") or {}

    name = record.get("name")

    if not name:
        name_data = person_data.get("name") or {}
        given = (name_data.get("given-names") or {}).get("value", "")
        family = (name_data.get("family-name") or {}).get("value", "")
        name = f"{given} {family}".strip()

    person = create_scientist(
        "ORCID",
        record.get("orcid"),
        name,
        record.get("orcid")
    )

    # Preserve public ORCID education and employment metadata.
    activities = raw.get("activities-summary") or {}

    education = (
        activities.get("educations", {})
        .get("affiliation-group", [])
    )

    employment = (
        activities.get("employments", {})
        .get("affiliation-group", [])
    )

    for group in education + employment:
        for item in group.get("summaries", []):
            affiliation = item.get("employment-summary") or item.get(
                "education-summary"
            ) or {}

            org = affiliation.get("organization", {})
            org_name = org.get("name")

            if org_name:
                person["institutions"].append(org_name)

    biography = record.get("biography")

    if biography:
        person["orcid_biography"] = biography


# --------------------------------------------------
# NOBEL
# --------------------------------------------------

for record in nobel:
    person = create_scientist(
        "Nobel",
        record.get("laureate_id"),
        record.get("name"),
        birth=record.get("birth_date"),
        death=record.get("death_date")
    )

    if record.get("laureate_id"):
        person["nobel_ids"].append(record["laureate_id"])

    person["awards"].extend(record.get("prizes", []))
    person["institutions"].extend(record.get("affiliations", []))


# --------------------------------------------------
# WIKIDATA
# --------------------------------------------------

for record in wikidata:
    person = create_scientist(
        "Wikidata",
        record.get("scientist_id"),
        record.get("name"),
        birth=record.get("birth_date"),
        death=record.get("death_date")
    )

    if record.get("scientist_id"):
        person["wikidata_ids"].append(record["scientist_id"])


# --------------------------------------------------
# CLEAN SCIENTIST RECORDS
# --------------------------------------------------

for person in scientists.values():
    for field in [
        "research_fields",
        "occupations",
        "institutions",
        "openalex_ids",
        "wikidata_ids",
        "nobel_ids",
        "sources"
    ]:
        person[field] = clean_list(person[field])

    person["awards"] = list({
        json.dumps(award, sort_keys=True, ensure_ascii=False): award
        for award in person["awards"]
    }.values())


# --------------------------------------------------
# NORMALIZE PUBLICATIONS
# --------------------------------------------------

publications = []
seen_dois = set()

for record in crossref:
    doi = record.get("doi")

    if not doi:
        continue

    doi_key = doi.lower().strip()

    if doi_key in seen_dois:
        continue

    seen_dois.add(doi_key)

    authors = []

    for author in record.get("authors", []):
        authors.append({
            "given": author.get("given"),
            "family": author.get("family"),
            "orcid": normalize_orcid(author.get("orcid"))
        })

    publication = {
        "publication_id": make_id("publication", doi_key),
        "doi": doi,
        "title": record.get("title"),
        "authors": authors,
        "published": record.get("published"),
        "type": record.get("type"),
        "publisher": record.get("publisher"),
        "source": "Crossref",
        "source_url": record.get("source_url")
    }

    publications.append(publication)


# --------------------------------------------------
# SOURCE MAPPING DEDUPLICATION
# --------------------------------------------------

mapping_dict = {}

for item in source_mapping:
    key = (item["source"], item["source_id"])
    mapping_dict[key] = item

source_mapping = list(mapping_dict.values())


# --------------------------------------------------
# VALIDATION
# --------------------------------------------------

missing_names = sum(
    1 for p in scientists.values() if not p.get("name")
)

missing_ids = sum(
    1 for p in scientists.values() if not p.get("scientist_id")
)

duplicate_dois = len(crossref) - len(publications)

source_counts = Counter()

for person in scientists.values():
    for source in person["sources"]:
        source_counts[source] += 1

report = {
    "domain": "scientists",
    "raw_counts": {
        "openalex": len(openalex),
        "wikidata": len(wikidata),
        "nobel": len(nobel),
        "orcid": len(orcid),
        "crossref": len(crossref)
    },
    "processed_counts": {
        "unique_scientists": len(scientists),
        "unique_publications": len(publications),
        "source_mapping_records": len(source_mapping)
    },
    "validation": {
        "scientists_missing_names": missing_names,
        "scientists_missing_ids": missing_ids,
        "duplicate_publications_removed": duplicate_dois,
        "all_scientist_ids_unique": (
            len({p["scientist_id"] for p in scientists.values()})
            == len(scientists)
        )
    },
    "scientists_by_source": dict(source_counts),
    "notes": [
        "Name-only matching is not used.",
        "Cross-source matching uses ORCID or exact name plus birth year.",
        "Wikidata records without names remain separate until entity resolution.",
        "Crossref authors are publication metadata, not verified scientist identities.",
        "Citation counts and h-index are descriptive metrics, not quality measures."
    ]
}


# --------------------------------------------------
# SAVE OUTPUTS
# --------------------------------------------------

write_jsonl(
    OUT / "scientists.jsonl",
    list(scientists.values())
)

write_jsonl(
    OUT / "publications.jsonl",
    publications
)

write_jsonl(
    OUT / "scientist_source_mapping.jsonl",
    source_mapping
)

with (OUT / "preprocessing_report.json").open(
    "w", encoding="utf-8"
) as f:
    json.dump(report, f, indent=4, ensure_ascii=False)


print("\n========== PREPROCESSING COMPLETE ==========")
print("Unique scientists:", len(scientists))
print("Unique publications:", len(publications))
print("Source mappings:", len(source_mapping))
print("Missing scientist names:", missing_names)
print("Duplicate DOIs removed:", duplicate_dois)
print("\nOutput directory:", OUT)
print("\nReport:")
print(json.dumps(report, indent=2))
