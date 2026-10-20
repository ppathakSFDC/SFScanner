from pathlib import Path
from functools import lru_cache

SKILLS_BASE = Path("/Users/p.pathak/Documents/Cloud")

# Map topic key → skill file path
_SKILL_PATHS = {
    "apex":                  SKILLS_BASE / "apex" / "SKILL.md",
    "bre":                   SKILLS_BASE / "bre" / "SKILL.md",
    "constraint_model":      SKILLS_BASE / "constraint-model" / "SKILL.md",
    "dataraptor":            SKILLS_BASE / "data-mappers" / "SKILL.md",
    "flow":                  SKILLS_BASE / "flow" / "SKILL.md",
    "integration_procedure": SKILLS_BASE / "integration-procedure" / "SKILL.md",
    "omniscript":            SKILLS_BASE / "omniscript" / "SKILL.md",
    "rca_product":           SKILLS_BASE / "rca-product-creation" / "SKILL.md",
}


def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter (--- ... ---) from markdown."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


@lru_cache(maxsize=None)
def get_skill(topic: str) -> str:
    """Return skill content for a topic key, stripped of frontmatter. Empty string if not found."""
    path = _SKILL_PATHS.get(topic)
    if not path or not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8"))


# Keywords that map a user message to a skill topic
_TOPIC_KEYWORDS: list[tuple[str, list[str]]] = [
    ("apex",    ["apex", ".cls", "trigger", "soql", "dml", "governor", "batch",
                 "queueable", "schedulable", "invocable", "@future", "testmethod",
                 "@istest", "bulkif", "sosl", "visualforce"]),
    ("omniscript", ["omniscript", "omni script", "omniprocess", "omnistudio", "vlocity script",
                    "lwc omniscript", "omni step", "omni element"]),
    ("dataraptor", ["dataraptor", "data raptor", "dr extract", "dr load", "dr transform",
                    "turbo extract", "drbundle", "dataraptors"]),
    ("integration_procedure", ["integration procedure", "integrationprocedure", "omniip",
                               "ip action", "integration proc"]),
    ("flow",    ["flow", "process builder", "workflow rule", "autolaunched flow",
                 "record-triggered", "screen flow", "scheduled flow", "platform event flow"]),
    ("bre",     ["bre", "business rule", "decision table", "decision matrix",
                 "expression set", "rule group", "rule engine", "business rules engine"]),
    ("constraint_model", ["constraint model", "constraint rule", "compatibility rule",
                          "cardinality", "eligibility rule", "product constraint",
                          "configuration rule"]),
    ("rca_product",      ["rca", "revenue cloud", "product creation", "product catalog",
                          "product definition", "attribute category", "attribute definition",
                          "product attribute", "price book", "pricing rule", "product relationship",
                          "bundle", "product group", "product publish", "rca product",
                          "revenue cloud advanced", "catalog product", "product configuration"]),
]


def detect_topics(message: str) -> list[str]:
    """Return ordered list of skill topics relevant to the message (most specific first)."""
    msg = message.lower()
    matched: list[str] = []
    for topic, keywords in _TOPIC_KEYWORDS:
        if any(kw in msg for kw in keywords):
            matched.append(topic)
    return matched


def skill_for_message(message: str, max_skills: int = 2) -> str:
    """Return concatenated skill content for the topics detected in a message."""
    topics = detect_topics(message)[:max_skills]
    parts = [get_skill(t) for t in topics if get_skill(t)]
    if not parts:
        return ""
    sep = "\n\n---\n\n"
    return sep.join(parts)
