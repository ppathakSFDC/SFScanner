import re
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


# Objects known to grow large in production orgs
_LARGE_OBJECTS = {
    'Account', 'Contact', 'Lead', 'Case', 'Opportunity', 'Task', 'Event',
    'ContentVersion', 'ContentDocument', 'EmailMessage', 'FeedItem',
    'ActivityHistory', 'CaseComment', 'OpportunityLineItem', 'Order',
    'OrderItem', 'Quote', 'QuoteLineItem', 'Asset', 'ServiceContract',
    'CampaignMember', 'User', 'AuditTrail', 'ApexLog',
}

# Fields that are NOT indexed by default in Salesforce
_NON_INDEXED_FIELDS = {
    'name', 'description', 'lastmodifieddate', 'createddate', 'systemmodstamp',
    'lastname', 'firstname', 'email', 'phone', 'title', 'department',
    'billingstreet', 'billingcity', 'mailingstreet', 'mailingcity',
    'subject', 'body', 'textbody', 'htmlbody', 'comments',
}


class SOQLScanner(BaseScanner):
    """Extracts and analyzes SOQL queries from Apex class bodies."""

    component_type = ComponentType.SOQL

    # Matches [SELECT ... ] blocks, including multi-line
    _SOQL_RE = re.compile(r'\[(\s*SELECT\b[^\]]+)\]', re.IGNORECASE | re.DOTALL)

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for cls in components:
            name = cls.get("Name", "Unknown")
            body = cls.get("Body", "") or ""
            cid = cls.get("Id")
            if not body or '[SELECT' not in body.upper():
                continue
            findings.extend(self._analyze_class(name, body, cid))
        return findings

    # ── per-class ────────────────────────────────────────────────────────────

    def _analyze_class(self, cls_name: str, body: str, cid: str) -> list[Finding]:
        findings = []
        char_to_line = self._build_line_map(body)

        # Track which rule fired per class to avoid flooding
        fired: set[str] = set()

        for m in self._SOQL_RE.finditer(body):
            raw = m.group(1).strip()
            q = ' '.join(raw.split())  # flatten whitespace
            lineno = char_to_line(m.start())

            for rule_id, rule_name, sev, desc, fix in self._check_query(q):
                if rule_id in fired:
                    continue
                fired.add(rule_id)
                findings.append(self._finding(
                    cls_name, rule_id, rule_name, sev, desc,
                    component_id=cid,
                    location=f"line ~{lineno}",
                    current_code=f"[{q}]",
                    suggested_fix=fix,
                    impact=_IMPACTS.get(rule_id, ''),
                    effort="low",
                ))

        return findings

    # ── per-query checks ─────────────────────────────────────────────────────

    def _check_query(self, q: str) -> list[tuple]:
        issues = []
        qu = q.upper()
        obj = self._object(q)
        fields = self._fields(q)
        has_where = 'WHERE' in qu
        has_limit = 'LIMIT' in qu
        is_aggregate = bool(re.search(r'\bCOUNT\s*\(', qu))

        # SOQL-001 — Missing LIMIT
        if not has_limit and not is_aggregate:
            issues.append((
                'SOQL-001', 'Missing LIMIT Clause', Severity.HIGH,
                f"Query on '{obj}' has no LIMIT. Could return thousands of rows and exhaust heap.",
                f"Add LIMIT to cap the result set:\n[{q} LIMIT 200]",
            ))

        # SOQL-002 — No WHERE clause (full table scan)
        if not has_where and not is_aggregate:
            sev = Severity.HIGH if obj in _LARGE_OBJECTS else Severity.MEDIUM
            issues.append((
                'SOQL-002', 'Full Table Scan — No WHERE Clause', sev,
                f"Query on '{obj}' has no WHERE filter — fetches every record in the table.",
                f"Add a selective filter:\n[{q} WHERE IsActive = true LIMIT 200]",
            ))

        # SOQL-003 — Leading wildcard LIKE
        if re.search(r"LIKE\s+'%[^']+", q, re.IGNORECASE):
            issues.append((
                'SOQL-003', 'Leading Wildcard in LIKE', Severity.HIGH,
                "LIKE '%value' or LIKE '%value%' with a leading % disables index use, "
                "forcing a full table scan on every call.",
                "Use a trailing wildcard 'value%' where possible:\n"
                "  WHERE Name LIKE 'Acme%'\n"
                "Or switch to SOSL for full-text search:\n"
                "  FIND {Acme*} IN NAME FIELDS RETURNING Account(Id, Name)",
            ))

        # SOQL-004 — NOT IN
        if re.search(r'\bNOT\s+IN\b', q, re.IGNORECASE):
            issues.append((
                'SOQL-004', 'NOT IN Operator (Non-Selective)', Severity.MEDIUM,
                "NOT IN cannot use standard indexes. Salesforce scans all records and "
                "excludes non-matches — very slow on large tables.",
                "Re-express as a positive filter when possible:\n"
                "  -- Instead of: WHERE Stage NOT IN ('Closed Won', 'Closed Lost')\n"
                "  -- Use: WHERE IsClosed = false\n"
                "If NOT IN is unavoidable, add a custom index on the field.",
            ))

        # SOQL-005 — Inequality operators != / <>
        if re.search(r'\s(!=|<>)\s', q):
            issues.append((
                'SOQL-005', 'Inequality Operator != (Non-Selective)', Severity.MEDIUM,
                "!= and <> cannot use standard indexes. Salesforce must scan all rows "
                "and exclude non-matching ones.",
                "Rewrite with IN using the known positive values:\n"
                "  -- Instead of: WHERE Status != 'Inactive'\n"
                "  -- Use: WHERE Status IN ('Active', 'Pending')",
            ))

        # SOQL-006 — OR on same field (use IN instead)
        m = re.search(r'(\w+)\s*=\s*\'[^\']*\'\s+OR\s+\1\s*=\s*\'', q, re.IGNORECASE)
        if m:
            field = m.group(1)
            issues.append((
                'SOQL-006', 'OR Conditions — Use IN Instead', Severity.LOW,
                f"Multiple OR conditions on '{field}' can be merged into a single IN clause.",
                f"Replace:\n  WHERE {field} = 'A' OR {field} = 'B'\nWith:\n  WHERE {field} IN ('A', 'B')",
            ))

        # SOQL-007 — Large OFFSET
        om = re.search(r'\bOFFSET\s+(\d+)', q, re.IGNORECASE)
        if om and int(om.group(1)) > 1000:
            offset_val = om.group(1)
            issues.append((
                'SOQL-007', f'Large OFFSET {offset_val} — Slow Pagination', Severity.HIGH,
                f"OFFSET {offset_val} forces Salesforce to scan and discard {offset_val} rows on every request. "
                "Performance degrades linearly with offset size (OFFSET 10000 ≈ 10× slower).",
                "Use keyset (cursor) pagination with Id ordering:\n"
                "  // First page\n"
                f"  [{self._object(q)} records] = [SELECT Id FROM {obj} ORDER BY Id LIMIT 200];\n"
                "  // Next page — store lastId from previous result\n"
                f"  [SELECT Id FROM {obj} WHERE Id > :lastId ORDER BY Id LIMIT 200]",
            ))

        # SOQL-008 — Too many fields selected
        if len(fields) > 15:
            issues.append((
                'SOQL-008', f'Excessive Field Selection ({len(fields)} fields)', Severity.LOW,
                f"Query selects {len(fields)} fields. Fetching unused fields wastes heap and "
                "increases serialization time.",
                f"Select only fields you actually reference in code:\n"
                f"  [SELECT Id, Name, {', '.join(fields[:3])}, ... FROM {obj} ...]",
            ))

        # SOQL-009 — Deep relationship traversal (3+ dot levels)
        deep = re.findall(r'\b\w+\.\w+\.\w+\b', q)
        if deep:
            issues.append((
                'SOQL-009', 'Deep Relationship Traversal', Severity.MEDIUM,
                f"Query traverses 3+ relationship levels: {deep[0]}. "
                "Each additional level adds a join, increasing query time.",
                "Flatten the data model or fetch related records in a separate query:\n"
                "  // Instead of deeply nested traversal, use two queries + a Map",
            ))

        # SOQL-010 — Filtering on non-indexed field only
        where_m = re.search(r'\bWHERE\s+(\w+)\s*(?:=|LIKE|IN)', q, re.IGNORECASE)
        if where_m and has_where:
            filter_field = where_m.group(1).lower()
            if filter_field in _NON_INDEXED_FIELDS and not has_limit:
                issues.append((
                    'SOQL-010', f'Non-Indexed Filter Field: {where_m.group(1)}', Severity.HIGH,
                    f"Filtering on '{where_m.group(1)}' which is not indexed by default. "
                    "Salesforce will perform a full table scan on every execution.",
                    f"Options to fix:\n"
                    f"1. Add a custom index on {where_m.group(1)} via Salesforce Support\n"
                    f"2. Add a selective indexed field (e.g. Id, RecordType, OwnerId) to the WHERE clause\n"
                    f"3. Add LIMIT to reduce risk:\n"
                    f"   [{q} LIMIT 200]",
                ))

        return issues

    # ── helpers ───────────────────────────────────────────────────────────────

    def _object(self, q: str) -> str:
        m = re.search(r'\bFROM\s+(\w+)', q, re.IGNORECASE)
        return m.group(1) if m else 'Unknown'

    def _fields(self, q: str) -> list[str]:
        m = re.search(r'SELECT\s+(.+?)\s+FROM', q, re.IGNORECASE | re.DOTALL)
        if not m:
            return []
        return [f.strip() for f in m.group(1).split(',') if f.strip()]

    def _build_line_map(self, body: str):
        """Returns a function that maps char offset → 1-based line number."""
        newlines = [i for i, c in enumerate(body) if c == '\n']
        def lookup(pos: int) -> int:
            lo, hi = 0, len(newlines)
            while lo < hi:
                mid = (lo + hi) // 2
                if newlines[mid] < pos:
                    lo = mid + 1
                else:
                    hi = mid
            return lo + 1
        return lookup


_IMPACTS = {
    'SOQL-001': 'Can return 50,000+ rows, exceeding row governor limits and crashing the transaction.',
    'SOQL-002': 'Full table scan — query time grows linearly with org data volume.',
    'SOQL-003': 'Full table scan on every execution — 10×–100× slower than an indexed lookup.',
    'SOQL-004': 'Full table scan; gets worse as data grows. Risk of UNABLE_TO_LOCK_ROW timeouts.',
    'SOQL-005': 'Non-indexed scan on large tables can cause query timeout (>120 s).',
    'SOQL-006': 'Minor: readability and Salesforce query optimizer hint improvement.',
    'SOQL-007': 'Response time grows linearly with offset. OFFSET 10,000 scans 10,000 rows before returning any.',
    'SOQL-008': 'Unnecessary heap consumption; increases risk of heap-size limit (6 MB) breaches.',
    'SOQL-009': 'Each extra relationship join adds latency; 3+ levels often cause query timeouts in large orgs.',
    'SOQL-010': 'Salesforce performs a full table scan instead of an index lookup — very slow at scale.',
}
