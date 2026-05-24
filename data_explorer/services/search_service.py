from rapidfuzz import fuzz, process

from data_explorer.services.search_data import get_search_entries

def entry_text(entry: dict) -> str:
    """
    Convert a single entry dict into one searchable string.
    We combine title + summary + keywords, then lowercase it for consistent matching.
    """
    # Get the title; if missing/None, use "" instead; strip whitespace.
    title = (entry.get("title") or "").strip()

    # Get the summary; if missing/None, use "" instead; strip whitespace.
    summary = (entry.get("summary") or "").strip()

    # Get keywords list; if missing/None, use []; join into one string; strip whitespace.
    keywords = " ".join(entry.get("keywords") or []).strip()

    # Combine non-empty parts with spaces, then casefold for robust lowercase matching.
    return " ".join(part for part in (title, summary, keywords) if part).casefold()


def search_entries(query: str, limit: int = 10, score_cutoff: int = 60) -> list[dict]:
    """
    Fuzzy-search entries using RapidFuzz.
    Returns up to `limit` entries whose match score >= `score_cutoff`,
    each entry annotated with a "score" field.
    """
    # Load all entries we can search across
    entries = get_search_entries()

    # If there's no query text OR no entries to search, return no results.
    if not query or not entries:
        return []

    # Build the list of searchable strings (one per entry) in the same order as `entries`.
    choices = [entry_text(e) for e in entries]

    # Run fuzzy matching
    matches = process.extract(
        query.casefold(),   # normalize query casing for consistent matching
        choices,            # list of strings to match against
        # matching algorithm
        scorer=fuzz.WRatio,
        limit=limit,        # return at most this many matches
        score_cutoff=score_cutoff,  # ignore anything below this score
    )

    # Convert RapidFuzz match tuples into actual entry dicts (plus their score).
    results: list[dict] = []
    for _matched_text, score, idx in matches:
        # Copy the original entry
        entry = dict(entries[idx])

        # Attach the match score so callers can see how strong the match was.
        entry["score"] = score

        # Collect the annotated entry
        results.append(entry)

    # sort by title ascending (case-insensitive) ...
    results.sort(key=lambda e: e.get("title", "").casefold())
    # then sort by score descending.
    results.sort(key=lambda e: e["score"], reverse=True)

    # Return the sorted, annotated matches.
    return results
