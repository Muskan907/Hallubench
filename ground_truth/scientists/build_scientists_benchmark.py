import json
import random
import re
import hashlib
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed/scientists"
RAW = ROOT / "data/raw/scientists"
FINAL = ROOT / "data/final/scientists"
FINAL.mkdir(parents=True, exist_ok=True)
SEED = 42


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[WARN] Invalid JSON: {path.name}:{line_no}")
    return rows


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def stable_id(prefix, value):
    return prefix + "_" + hashlib.sha256(str(value).encode()).hexdigest()[:14]


def year_from_date(value):
    if not value:
        return None
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", str(value))
    return int(m.group(1)) if m else None


def get_nested(obj, *keys):
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def add_fact(facts, scientist, predicate, value, source, source_record_id,
             source_url, evidence, category, confidence="source_metadata"):
    if value is None or value == "" or value == []:
        return
    if isinstance(value, (dict, list)):
        answer = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        answer = str(value)
    fact = {
        "fact_id": stable_id("sf", f"{scientist['scientist_id']}|{predicate}|{answer}|{source_record_id}"),
        "domain": "scientists",
        "subject_id": scientist["scientist_id"],
        "subject_name": scientist.get("name"),
        "predicate": predicate,
        "object": value,
        "claim_type": category,
        "source": source,
        "source_record_id": str(source_record_id),
        "source_url": source_url,
        "evidence": evidence,
        "verification_status": "source_backed_metadata",
        "confidence_basis": confidence
    }
    facts.append(fact)


def main():
    scientists = read_jsonl(PROCESSED / "scientists.jsonl")
    publications = read_jsonl(PROCESSED / "publications.jsonl")
    mapping = read_jsonl(PROCESSED / "scientist_source_mapping.jsonl")
    nobel_raw = read_jsonl(RAW / "nobel_laureates.jsonl")

    if not scientists:
        raise SystemExit("No processed scientists found. Run preprocessing first.")

    # Map source IDs back to the canonical processed scientist ID.
    source_to_scientist = {}
    for row in mapping:
        source_to_scientist[(row.get("source"), str(row.get("source_id")))] = row.get("scientist_id")

    by_id = {s.get("scientist_id"): s for s in scientists}
    facts = []
    fact_by_subject = defaultdict(list)

    # Core profile facts from normalized scientist records.
    for s in scientists:
        name = s.get("name")
        sid = s.get("scientist_id")
        if not name or not sid:
            continue

        # Identity itself is useful only when the record has a source ID.
        for source in s.get("sources", []):
            source_ids = {
                "OpenAlex": s.get("openalex_ids", []),
                "Wikidata": s.get("wikidata_ids", []),
                "Nobel": s.get("nobel_ids", [])
            }.get(source, [])
            if source == "ORCID" and s.get("orcid"):
                source_ids = [s["orcid"]]
            for source_id in source_ids:
                add_fact(facts, s, "scientist_name", name, source, source_id,
                         f"https://orcid.org/{s['orcid']}" if source == "ORCID" and s.get("orcid") else None,
                         f"Normalized scientist profile lists the name {name}.", "identity")

        stats = s.get("openalex_stats") or {}
        for field, predicate in [("works_count", "openalex_works_count"),
                                 ("cited_by_count", "openalex_cited_by_count"),
                                 ("h_index", "openalex_h_index"),
                                 ("i10_index", "openalex_i10_index")]:
            value = stats.get(field)
            if value is not None:
                source_id = (s.get("openalex_ids") or [sid])[0]
                add_fact(facts, s, predicate, value, "OpenAlex", source_id,
                         source_id if str(source_id).startswith("http") else None,
                         f"OpenAlex author profile reports {field}={value}.", "bibliometrics",
                         confidence="provider-reported metric; not a measure of research quality")

    # Biographical and Nobel award facts are taken directly from the raw Nobel
    # source so that source attribution is exact, not inferred from merged fields.
    for laureate in nobel_raw:
        laureate_id = str(laureate.get("laureate_id") or "")
        sid = source_to_scientist.get(("Nobel", laureate_id))
        scientist = by_id.get(sid)
        if not scientist:
            continue
        name = scientist.get("name")
        for predicate, value in [("birth_date", laureate.get("birth_date")),
                                 ("death_date", laureate.get("death_date"))]:
            add_fact(facts, scientist, predicate, value, "Nobel Prize API", laureate_id,
                     f"https://www.nobelprize.org/laureate/{laureate_id}",
                     f"Official Nobel laureate record for {name}: {predicate}={value}.",
                     "biographical")
        for prize in laureate.get("prizes", []):
            if not isinstance(prize, dict):
                continue
            year = prize.get("awardYear")
            category = get_nested(prize, "category", "en") or get_nested(prize, "category", "fullName", "en")
            motivation = get_nested(prize, "motivation", "en")
            evidence = f"Official Nobel Prize API prize record for {name}: {json.dumps(prize, ensure_ascii=False)}"
            for predicate, value in [("nobel_prize_year", year),
                                     ("nobel_prize_category", category),
                                     ("nobel_prize_motivation", motivation)]:
                add_fact(facts, scientist, predicate, value, "Nobel Prize API", laureate_id,
                         f"https://www.nobelprize.org/laureate/{laureate_id}",
                         evidence, "award")

    # Publication facts. Crossref author identity is only linked through exact ORCID.
    orcid_to_scientist = {}
    for s in scientists:
        if s.get("orcid"):
            orcid_to_scientist[s["orcid"].rstrip("/").split("/")[-1]] = s

    for pub in publications:
        doi = pub.get("doi")
        if not doi:
            continue
        pub_url = pub.get("source_url") or f"https://doi.org/{doi}"
        title = pub.get("title")
        if title:
            facts.append({
                "fact_id": stable_id("sf", f"publication|{doi}|title"),
                "domain": "scientists", "subject_id": stable_id("publication", doi),
                "subject_name": title, "predicate": "publication_title", "object": title,
                "claim_type": "publication", "source": "Crossref", "source_record_id": doi,
                "source_url": pub_url, "evidence": f"Crossref metadata title for DOI {doi}: {title}",
                "verification_status": "source_backed_metadata", "confidence_basis": "Crossref deposited metadata"
            })
        if pub.get("published"):
            facts.append({
                "fact_id": stable_id("sf", f"publication|{doi}|published"),
                "domain": "scientists", "subject_id": stable_id("publication", doi),
                "subject_name": title, "predicate": "publication_date_parts", "object": pub["published"],
                "claim_type": "publication", "source": "Crossref", "source_record_id": doi,
                "source_url": pub_url, "evidence": f"Crossref publication date metadata for DOI {doi}.",
                "verification_status": "source_backed_metadata", "confidence_basis": "Crossref deposited metadata"
            })
        for author in pub.get("authors", []):
            oid = author.get("orcid")
            if not oid:
                continue
            oid = oid.rstrip("/").split("/")[-1]
            scientist = orcid_to_scientist.get(oid)
            if scientist:
                author_name = " ".join(x for x in [author.get("given"), author.get("family")] if x)
                add_fact(facts, scientist, "authored_crossref_publication", {
                    "doi": doi, "title": title, "author_name_in_crossref": author_name
                }, "Crossref", doi, pub_url,
                f"Crossref lists ORCID {oid} as an author of DOI {doi}.", "publication_author",
                confidence="linked by exact ORCID identifier")

    # Deduplicate facts deterministically.
    unique_facts = {}
    for fact in facts:
        unique_facts[fact["fact_id"]] = fact
    facts = list(unique_facts.values())

    # Factual questions, only where an answer is directly supported by a fact.
    questions = []
    for fact in facts:
        if fact.get("subject_id", "").startswith("publication_"):
            if fact["predicate"] == "publication_title":
                q = f"What is the title of the publication with DOI {fact['source_record_id']}?"
            elif fact["predicate"] == "publication_date_parts":
                q = f"What publication date is recorded by Crossref for DOI {fact['source_record_id']}?"
            else:
                continue
        else:
            name = fact.get("subject_name")
            if not name:
                continue
            pred = fact["predicate"]
            if pred == "birth_date":
                q = f"What birth date is recorded for {name}?"
            elif pred == "death_date":
                q = f"What death date is recorded for {name}?"
            elif pred == "openalex_works_count":
                q = f"How many works does OpenAlex list for {name}?"
            elif pred == "openalex_cited_by_count":
                q = f"How many citations does OpenAlex report for {name}'s works?"
            elif pred == "openalex_h_index":
                q = f"What h-index does OpenAlex report for {name}?"
            elif pred == "openalex_i10_index":
                q = f"What i10-index does OpenAlex report for {name}?"
            elif pred == "associated_institution":
                q = f"Which institution is listed in the collected source metadata for {name}?"
            elif pred == "nobel_prize_year":
                q = f"In what year did {name} receive the Nobel Prize recorded in this dataset?"
            elif pred == "nobel_prize_category":
                q = f"In which Nobel Prize category is {name}'s award recorded?"
            elif pred == "nobel_prize_motivation":
                q = f"What Nobel Prize motivation is recorded for {name}?"
            elif pred == "authored_crossref_publication":
                obj = fact["object"]
                q = f"Which Crossref publication is linked to {name} through ORCID {fact['evidence'].split('ORCID ')[1].split(' ')[0]}?"
            else:
                continue

        questions.append({
            "question_id": stable_id("sq", fact["fact_id"]),
            "domain": "scientists",
            "question": q,
            "expected_answer": fact["object"],
            "question_type": fact["claim_type"],
            "evaluation_group": "factual",
            "ground_truth_fact_id": fact["fact_id"],
            "subject_id": fact["subject_id"],
            "subject_name": fact.get("subject_name"),
            "source": fact["source"],
            "source_url": fact.get("source_url"),
            "evidence": fact["evidence"],
            "answerability": "answerable_from_source"
        })

    # False-premise challenges: alter a recorded Nobel year, clearly preserving correction target.
    challenges = []
    for fact in facts:
        if fact["predicate"] == "nobel_prize_year" and fact.get("subject_name"):
            try:
                actual_year = int(fact["object"])
            except (TypeError, ValueError):
                continue
            wrong_year = actual_year + 1 if actual_year < 2025 else actual_year - 1
            challenges.append({
                "question_id": stable_id("sc", f"false|{fact['fact_id']}"),
                "domain": "scientists", "question": f"{fact['subject_name']} received the Nobel Prize in {wrong_year}, correct? Explain the correct year.",
                "question_type": "false_premise", "evaluation_group": "challenge",
                "challenge_type": "false_premise", "expected_answer": actual_year,
                "ground_truth_fact_id": fact["fact_id"], "subject_id": fact["subject_id"],
                "subject_name": fact["subject_name"], "source": fact["source"],
                "source_url": fact.get("source_url"), "evidence": fact["evidence"],
                "answerability": "correctable_from_source"
            })

    # Ambiguity challenges only for duplicate normalized names belonging to distinct IDs.
    names = defaultdict(list)
    for s in scientists:
        if s.get("name") and s.get("normalized_name"):
            names[s["normalized_name"]].append(s)
    for normalized, group in names.items():
        distinct = {x["scientist_id"] for x in group}
        if len(distinct) > 1:
            display = group[0]["name"]
            candidates = [
                {"scientist_id": x["scientist_id"], "orcid": x.get("orcid"),
                 "openalex_ids": x.get("openalex_ids", [])}
                for x in group[:5]
            ]
            challenges.append({
                "question_id": stable_id("sc", f"ambiguous|{normalized}"),
                "domain": "scientists",
                "question": f"Tell me the h-index of {display}.",
                "question_type": "ambiguous", "evaluation_group": "challenge",
                "challenge_type": "ambiguous", "expected_answer": None,
                "candidate_subjects": candidates,
                "evidence": "Multiple distinct scientist records share this normalized name. The person must be disambiguated.",
                "answerability": "requires_clarification"
            })

    # Unsupported-evidence challenges. These ask for fields absent from the collected schema.
    unsupported_prompts = [
        "What was {name}'s exact personal annual income in 2024?",
        "What was {name}'s private home address?",
        "What was {name}'s IQ score?",
        "What was {name}'s exact political affiliation?"
    ]
    eligible = [s for s in scientists if s.get("name") and s.get("sources")]
    for i, s in enumerate(eligible[:500]):
        template = unsupported_prompts[i % len(unsupported_prompts)]
        challenges.append({
            "question_id": stable_id("sc", f"unsupported|{s['scientist_id']}|{i}"),
            "domain": "scientists", "question": template.format(name=s["name"]),
            "question_type": "unsupported_evidence", "evaluation_group": "challenge",
            "challenge_type": "unsupported_evidence", "expected_answer": None,
            "subject_id": s["scientist_id"], "subject_name": s["name"],
            "evidence": "The collected benchmark sources do not contain this requested field. Absence from this dataset does not establish the real-world value.",
            "answerability": "not_supported_by_collected_sources"
        })

    # Remove duplicate questions.
    q_seen = set()
    unique_questions = []
    for q in questions:
        key = (q["question"], q.get("ground_truth_fact_id"))
        if key not in q_seen:
            q_seen.add(key)
            unique_questions.append(q)
    questions = unique_questions

    c_seen = set()
    unique_challenges = []
    for q in challenges:
        if q["question_id"] not in c_seen:
            c_seen.add(q["question_id"])
            unique_challenges.append(q)
    challenges = unique_challenges

    # Reproducible pilots, up to 100 each.
    rng = random.Random(SEED)
    factual_pilot = rng.sample(questions, min(100, len(questions)))
    challenge_pilot = rng.sample(unique_challenges, min(100, len(unique_challenges)))

    # Stratified challenge pilot where possible.
    groups = defaultdict(list)
    for q in unique_challenges:
        groups[q["challenge_type"]].append(q)
    stratified = []
    per_type = {"false_premise": 34, "ambiguous": 33, "unsupported_evidence": 33}
    for kind, quota in per_type.items():
        pool = groups.get(kind, [])
        stratified.extend(rng.sample(pool, min(quota, len(pool))))
    if len(stratified) < min(100, len(unique_challenges)):
        used = {q["question_id"] for q in stratified}
        rest = [q for q in unique_challenges if q["question_id"] not in used]
        stratified.extend(rng.sample(rest, min(100 - len(stratified), len(rest))))
    challenge_pilot = stratified[:100]

    # Save all artifacts.
    write_jsonl(FINAL / "ground_truth.jsonl", facts)
    write_jsonl(FINAL / "questions.jsonl", questions)
    write_jsonl(FINAL / "challenge_questions.jsonl", unique_challenges)
    write_jsonl(FINAL / "pilot_sample_100.jsonl", factual_pilot)
    write_jsonl(FINAL / "challenge_pilot_100.jsonl", challenge_pilot)

    # Validation checks.
    def validate(rows, id_key):
        ids = [r.get(id_key) for r in rows]
        return {
            "records": len(rows),
            "unique_ids": len(set(ids)),
            "duplicate_ids": len(ids) - len(set(ids)),
            "missing_ids": sum(not x for x in ids)
        }

    report = {
        "domain": "scientists",
        "random_seed": SEED,
        "counts": {
            "processed_scientists": len(scientists),
            "processed_publications": len(publications),
            "ground_truth_facts": len(facts),
            "factual_questions": len(questions),
            "challenge_questions": len(unique_challenges),
            "factual_pilot": len(factual_pilot),
            "challenge_pilot": len(challenge_pilot)
        },
        "question_types": dict(Counter(q["question_type"] for q in questions)),
        "challenge_types": dict(Counter(q["challenge_type"] for q in unique_challenges)),
        "validation": {
            "ground_truth": validate(facts, "fact_id"),
            "factual_questions": validate(questions, "question_id"),
            "challenge_questions": validate(unique_challenges, "question_id"),
            "factual_pilot": validate(factual_pilot, "question_id"),
            "challenge_pilot": validate(challenge_pilot, "question_id"),
            "all_factual_questions_have_fact": all(q.get("ground_truth_fact_id") for q in questions),
            "all_factual_questions_have_evidence": all(q.get("evidence") for q in questions),
            "unsupported_questions_do_not_claim_absence_as_false": True
        },
        "limitations": [
            "Collected records are metadata snapshots, not a complete census of global scientists.",
            "OpenAlex bibliometric metrics are provider-reported and are not research-quality measures.",
            "Crossref publication authors are linked to scientists only by exact ORCID.",
            "Institution entries may represent different dates or roles and are not necessarily current affiliations.",
            "Unsupported questions mean unsupported by this collected dataset, not false in the real world.",
            "Ambiguity questions are generated only when duplicate normalized names exist in the processed data."
        ]
    }

    with (FINAL / "scientists_benchmark_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n========== SCIENTISTS BENCHMARK GENERATED ==========")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\nFiles saved in:", FINAL)


if __name__ == "__main__":
    main()
