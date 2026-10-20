import re
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class ApexScanner(BaseScanner):
    component_type = ComponentType.APEX

    SOQL_IN_LOOP = re.compile(r"\bfor\b[^{]*\{[^}]*\[SELECT\b", re.IGNORECASE | re.DOTALL)
    DML_IN_LOOP = re.compile(
        r"\bfor\b[^{]*\{[^}]*\b(insert|update|delete|upsert|merge|undelete)\b",
        re.IGNORECASE | re.DOTALL,
    )
    HARDCODED_ID = re.compile(r"['\"]([a-zA-Z0-9]{15}|[a-zA-Z0-9]{18})['\"]")
    SYSTEM_DEBUG = re.compile(r"System\.debug\s*\(", re.IGNORECASE)
    WITHOUT_SHARING = re.compile(r"\bwithout\s+sharing\b", re.IGNORECASE)
    NO_SHARING = re.compile(r"\bclass\s+\w+\s*\{", re.IGNORECASE)
    SHARING_DECLARED = re.compile(r"\b(with|without|inherited)\s+sharing\b", re.IGNORECASE)
    CATCH_EXCEPTION_EMPTY = re.compile(
        r"catch\s*\(\s*Exception\s+\w+\s*\)\s*\{\s*\}", re.IGNORECASE
    )
    HARDCODED_URL = re.compile(r"['\"]https?://[^'\"]{10,}['\"]", re.IGNORECASE)
    DML_STATEMENTS = re.compile(
        r"\b(insert|update|delete|upsert|merge|undelete)\s+\w+\s*;", re.IGNORECASE
    )
    SOQL_STATEMENTS = re.compile(r"\[SELECT\b", re.IGNORECASE)

    # New rules
    IS_TRIGGER  = re.compile(r'\btrigger\s+\w+\s+on\s+\w+', re.IGNORECASE)
    HAS_HANDLER = re.compile(r'(Handler|Service|TriggerHandler|Dispatcher|Manager)\s*\.(run|execute|handle|dispatch|process)', re.IGNORECASE)
    GET_ZERO    = re.compile(r'\.\s*get\s*\(\s*0\s*\)', re.IGNORECASE)
    IS_EMPTY_CHECK = re.compile(r'(\.isEmpty\(\)|\.size\(\)\s*[>!])', re.IGNORECASE)
    IS_TEST     = re.compile(r'@isTest', re.IGNORECASE)
    HAS_ASSERT  = re.compile(r'(System\.assert|Assert\.)', re.IGNORECASE)

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for cls in components:
            name = cls.get("Name", "Unknown")
            body = cls.get("Body", "") or ""
            cid = cls.get("Id")
            findings.extend(self._check_class(name, body, cid))
        return findings

    def _check_class(self, name: str, body: str, cid: str) -> list[Finding]:
        findings = []

        # SOQL in loops — critical
        if self._has_soql_in_loop(body):
            findings.append(self._finding(
                name, "APEX-001", "SOQL Inside Loop", Severity.CRITICAL,
                "SOQL query found inside a for/while loop. This hits governor limits quickly.",
                component_id=cid,
                current_code=self._extract_loop_snippet(body, "SELECT"),
                suggested_fix=(
                    "Move the SOQL query outside the loop. Collect IDs in the loop, "
                    "then query once:\n\nList<Id> ids = new List<Id>();\n"
                    "for (...) { ids.add(record.Id); }\n"
                    "Map<Id, SObject> recs = new Map<Id, SObject>([SELECT ... WHERE Id IN :ids]);"
                ),
                impact="Can exceed 100 SOQL per transaction limit, causing runtime exceptions.",
                effort="medium",
            ))

        # DML in loops — critical
        if self._has_dml_in_loop(body):
            findings.append(self._finding(
                name, "APEX-002", "DML Inside Loop", Severity.CRITICAL,
                "DML operation (insert/update/delete) found inside a loop.",
                component_id=cid,
                suggested_fix=(
                    "Collect records in a list inside the loop and perform a single "
                    "bulk DML operation after the loop:\n\n"
                    "List<SObject> toUpdate = new List<SObject>();\n"
                    "for (...) { toUpdate.add(rec); }\nupdate toUpdate;"
                ),
                impact="Exceeds 150 DML statements per transaction limit.",
                effort="medium",
            ))

        # No sharing keyword
        if not self.SHARING_DECLARED.search(body) and "class " in body.lower():
            findings.append(self._finding(
                name, "APEX-003", "Missing Sharing Declaration", Severity.HIGH,
                "Class has no 'with sharing' or 'without sharing' declaration. "
                "Defaults to without sharing, potentially exposing records.",
                component_id=cid,
                suggested_fix="Add 'with sharing' to the class declaration:\n\npublic with sharing class " + name + " { ... }",
                impact="May expose records the user should not access, violating org security model.",
                effort="low",
            ))

        # Without sharing — flag for review
        if self.WITHOUT_SHARING.search(body):
            findings.append(self._finding(
                name, "APEX-004", "Without Sharing Used", Severity.MEDIUM,
                "Class uses 'without sharing'. Verify this is intentional and documented.",
                component_id=cid,
                impact="Bypasses org sharing rules — all records accessible regardless of user permissions.",
                effort="low",
            ))

        # Empty catch blocks
        if self.CATCH_EXCEPTION_EMPTY.search(body):
            findings.append(self._finding(
                name, "APEX-005", "Empty Catch Block", Severity.HIGH,
                "An empty catch block silently swallows exceptions.",
                component_id=cid,
                suggested_fix=(
                    "Log the exception or rethrow it:\n\n"
                    "catch (Exception e) {\n"
                    "    System.debug(LoggingLevel.ERROR, e.getMessage());\n"
                    "    throw e; // or AuraHandledException\n}"
                ),
                impact="Errors go undetected, leading to silent data corruption or missed failures.",
                effort="low",
            ))

        # Excessive System.debug calls
        debug_count = len(self.SYSTEM_DEBUG.findall(body))
        if debug_count > 10:
            findings.append(self._finding(
                name, "APEX-006", "Excessive Debug Statements", Severity.LOW,
                f"Found {debug_count} System.debug() calls. These add overhead in production.",
                component_id=cid,
                suggested_fix="Use LoggingLevel.FINE or wrap in a custom Logger that checks a feature flag.",
                impact="Increases heap usage and log size, causing log truncation in production.",
                effort="low",
            ))

        # Hardcoded IDs
        hardcoded = self._find_hardcoded_ids(body)
        if hardcoded:
            findings.append(self._finding(
                name, "APEX-007", "Hardcoded Salesforce ID", Severity.HIGH,
                f"Hardcoded Salesforce record IDs found: {', '.join(hardcoded[:3])}",
                component_id=cid,
                suggested_fix=(
                    "Use Custom Metadata, Custom Settings, or query by DeveloperName instead "
                    "of hardcoding IDs. IDs differ between orgs and sandboxes."
                ),
                impact="Deployments to other orgs or sandboxes will break silently.",
                effort="medium",
            ))

        # Hardcoded URLs
        if self.HARDCODED_URL.search(body):
            findings.append(self._finding(
                name, "APEX-008", "Hardcoded URL", Severity.MEDIUM,
                "Hardcoded URL found in Apex class.",
                component_id=cid,
                suggested_fix="Store URLs in Custom Metadata or Named Credentials.",
                impact="Breaks when environment changes (sandbox vs production).",
                effort="low",
            ))

        # Large class — too many DML/SOQL (complexity proxy)
        soql_count = len(self.SOQL_STATEMENTS.findall(body))
        dml_count = len(self.DML_STATEMENTS.findall(body))
        if soql_count + dml_count > 20:
            findings.append(self._finding(
                name, "APEX-009", "High Database Operation Count", Severity.MEDIUM,
                f"Class has {soql_count} SOQL queries and {dml_count} DML statements. "
                "Consider splitting into service/repository layers.",
                component_id=cid,
                impact="Risk of hitting governor limits under bulk data scenarios.",
                effort="high",
            ))

        # APEX-010: Trigger without handler pattern
        if self.IS_TRIGGER.search(body) and not self.HAS_HANDLER.search(body):
            findings.append(self._finding(
                name, "APEX-010", "Trigger Without Handler Pattern", Severity.HIGH,
                f"Trigger '{name}' contains business logic directly instead of delegating to a handler class.",
                component_id=cid,
                suggested_fix=(
                    f"Create a handler class '{name}Handler' and call it:\n\n"
                    f"trigger {name} on Object (before insert, after insert) {{\n"
                    f"    {name}Handler.run(Trigger.new, Trigger.old, Trigger.operationType);\n}}"
                ),
                impact="Logic in triggers is hard to test, reuse, and maintain. Multiple triggers on same object cause unpredictable execution order.",
                effort="medium",
            ))

        # APEX-011: Null-unsafe SOQL result access (.get(0) without isEmpty check)
        get_zero_count = len(self.GET_ZERO.findall(body))
        is_empty_count = len(self.IS_EMPTY_CHECK.findall(body))
        if get_zero_count > 0 and get_zero_count > is_empty_count:
            findings.append(self._finding(
                name, "APEX-011", "Null-Unsafe List Index Access", Severity.HIGH,
                "Accessing index [0] on a list without checking if it's empty will throw a ListException.",
                component_id=cid,
                suggested_fix=(
                    "Always check before accessing:\n\n"
                    "List<Account> accounts = [SELECT Id FROM Account WHERE ...];\n"
                    "if (!accounts.isEmpty()) {\n    Account a = accounts.get(0);\n}"
                ),
                impact="Causes ListException: 'List index out of bounds: 0' in production when no records exist.",
                effort="low",
            ))

        # APEX-012: Test class without assertions
        if self.IS_TEST.search(body) and not self.HAS_ASSERT.search(body):
            findings.append(self._finding(
                name, "APEX-012", "Test Class Without Assertions", Severity.HIGH,
                f"Test class '{name}' contains no assertions. Tests pass vacuously without validating any behavior.",
                component_id=cid,
                suggested_fix=(
                    "Add assertions after the method under test:\n\n"
                    "System.assertEquals(expected, actual, 'Description of what was checked');\n"
                    "// Or use the modern Assert API:\n"
                    "Assert.areEqual(expected, actual, 'Description');"
                ),
                impact="Tests pass even if the method returns wrong values or throws no exception. No regression protection.",
                effort="low",
            ))

        # APEX-013: @AuraEnabled without AuraHandledException
        if "@AuraEnabled" in body and "AuraHandledException" not in body:
            findings.append(self._finding(
                name, "APEX-013", "@AuraEnabled Without Error Handling", Severity.HIGH,
                "@AuraEnabled method does not use AuraHandledException. LWC/Aura components will receive a generic error.",
                component_id=cid,
                suggested_fix=(
                    "Wrap the method body in try-catch:\n\n"
                    "@AuraEnabled\npublic static ReturnType methodName() {\n"
                    "    try {\n        // logic here\n"
                    "    } catch (Exception e) {\n"
                    "        throw new AuraHandledException(e.getMessage());\n    }\n}"
                ),
                impact="Unhandled exceptions expose raw error messages to the UI and crash the component.",
                effort="low",
            ))

        # APEX-014: Excessive Database.setSavepoint usage
        savepoint_count = len(re.findall(r'\bDatabase\.setSavepoint\b', body, re.IGNORECASE))
        if savepoint_count > 2:
            findings.append(self._finding(
                name, "APEX-014", "Excessive Database.setSavepoint Usage", Severity.MEDIUM,
                f"Excessive use of Database.setSavepoint ({savepoint_count} times). Each savepoint consumes DML statement quota.",
                component_id=cid,
                suggested_fix="Consolidate savepoints — only create one per transaction entry point and use a single rollback.",
                impact="Each setSavepoint counts as 1 DML statement against the 150-DML limit.",
                effort="low",
            ))

        # APEX-015: Dynamic SOQL string injection risk
        DSOQL_CONCAT = re.compile(r"Database\.(query|count)\s*\(\s*['\"].*\+", re.IGNORECASE)
        if DSOQL_CONCAT.search(body):
            findings.append(self._finding(
                name, "APEX-015", "Dynamic SOQL String Concatenation",
                Severity.CRITICAL,
                "Dynamic SOQL built with string concatenation is vulnerable to SOQL injection attacks.",
                component_id=cid,
                suggested_fix="Use bind variables (:varName) instead of string concatenation in SOQL queries.",
                impact="Attackers can manipulate SOQL queries to access unauthorized records or extract org data.",
                effort="medium",
            ))

        # APEX-016: Weak cryptographic hashing (MD5/SHA1)
        WEAK_HASH = re.compile(r"Crypto\.generateDigest\s*\(\s*['\"](?:MD5|SHA1|SHA-1)['\"]", re.IGNORECASE)
        if WEAK_HASH.search(body):
            findings.append(self._finding(
                name, "APEX-016", "Weak Cryptographic Hash Algorithm",
                Severity.HIGH,
                "MD5 and SHA-1 are cryptographically broken and should not be used for security purposes.",
                component_id=cid,
                suggested_fix="Replace with SHA-256 or SHA-512: Crypto.generateDigest('SHA-256', input)",
                impact="Weak hashing enables collision attacks and compromises password/data integrity checks.",
                effort="low",
            ))

        # APEX-017: HTTP callout without timeout
        HTTP_NO_TIMEOUT = re.compile(r"new\s+Http(?:Request)?\s*\(\s*\)", re.IGNORECASE)
        HTTP_TIMEOUT    = re.compile(r"\.setTimeout\s*\(", re.IGNORECASE)
        if HTTP_NO_TIMEOUT.search(body) and not HTTP_TIMEOUT.search(body):
            findings.append(self._finding(
                name, "APEX-017", "HTTP Callout Without Timeout",
                Severity.MEDIUM,
                "HTTP callouts without explicit timeout can hang threads and exhaust governor limits under slow/unreachable endpoints.",
                component_id=cid,
                suggested_fix="Set req.setTimeout(10000) (10s) before every Http.send() call.",
                impact="Hanging callout threads can cause cascading limit failures and org unresponsiveness.",
                effort="low",
            ))

        return findings

    def _has_soql_in_loop(self, body: str) -> bool:
        lines = body.split("\n")
        in_loop = 0
        for line in lines:
            stripped = line.strip()
            if re.match(r"\bfor\b|\bwhile\b", stripped, re.IGNORECASE):
                in_loop += 1
            if in_loop > 0 and "[SELECT" in line.upper():
                return True
            in_loop -= stripped.count("}")
            in_loop = max(0, in_loop)
        return False

    def _has_dml_in_loop(self, body: str) -> bool:
        dml_ops = {"insert", "update", "delete", "upsert", "merge", "undelete"}
        lines = body.split("\n")
        in_loop = 0
        for line in lines:
            stripped = line.strip().lower()
            if re.match(r"\bfor\b|\bwhile\b", stripped):
                in_loop += 1
            if in_loop > 0:
                for op in dml_ops:
                    if re.match(rf"\b{op}\b", stripped):
                        return True
            in_loop -= stripped.count("}")
            in_loop = max(0, in_loop)
        return False

    def _extract_loop_snippet(self, body: str, keyword: str) -> str:
        idx = body.upper().find(keyword)
        if idx == -1:
            return ""
        start = max(0, idx - 200)
        return body[start : idx + 100].strip()

    def _find_hardcoded_ids(self, body: str) -> list[str]:
        candidates = self.HARDCODED_ID.findall(body)
        # Filter to likely SF IDs (start with known key prefixes)
        sf_prefixes = {
            "001", "003", "005", "006", "007", "00D", "00E", "00G", "00N",
            "00Q", "00T", "012", "013", "014", "015", "016", "017", "0D5",
        }
        results = []
        for c in candidates:
            if len(c) in (15, 18) and c[:3] in sf_prefixes:
                results.append(c)
        return list(set(results))
