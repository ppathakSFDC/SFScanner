import re
import json
import httpx
from typing import Any

# PCM metadata-like objects that require the Tooling API for creation
_TOOLING_API_OBJECTS = {
    "ProductClassification",
    "ProductClassificationAttr",
    "ProductCatalog",
    "ProductCategory",
}

# Anthropic tool definitions
TOOL_DEFINITIONS = [
    {
        "name": "query_salesforce",
        "description": (
            "Run a read-only SOQL SELECT query against the connected Salesforce org. "
            "Use this to look up Cases, Accounts, Contacts, Products, Orders, and any other object. "
            "Always include a LIMIT clause. Use describe_object first if unsure of field names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "soql": {
                    "type": "string",
                    "description": "A valid SOQL SELECT statement. Must start with SELECT. Always include LIMIT <= 200."
                }
            },
            "required": ["soql"]
        }
    },
    {
        "name": "create_record",
        "description": (
            "Create a new record in Salesforce. Only permitted objects are allowed. "
            "Use describe_object first to confirm field API names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "API name of the Salesforce object, e.g. Product2, ProductRelatedComponent"
                },
                "fields": {
                    "type": "object",
                    "description": "Map of field API name to value for the new record"
                }
            },
            "required": ["object_name", "fields"]
        }
    },
    {
        "name": "describe_object",
        "description": (
            "Return the list of available fields on a Salesforce object. "
            "Call this before querying or creating records on unfamiliar objects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "API name of the Salesforce object, e.g. Case, Product2, ProductRelatedComponent"
                }
            },
            "required": ["object_name"]
        }
    }
]

# OpenAI-compatible tool definitions (for llmgw path)
TOOL_DEFINITIONS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        }
    }
    for t in TOOL_DEFINITIONS
]

# Objects permitted for create_record
# Full PCM object set from the Revenue Cloud deployment skill (dependency order: A→B→C→D→E→F→G→H)
_CREATE_ALLOWLIST = {
    # Lane A — Attribute framework
    "AttributeCategory",
    "AttributeDefinition",
    "AttributePicklist",
    "AttributePicklistValue",
    "AttrPicklistExcludedValue",
    "AttributeCategoryAttribute",
    # Lane B — Classification
    "ProductClassification",
    "ProductClassificationAttr",
    # Lane C — Catalog structure
    "ProductCatalog",
    "ProductCategory",
    "ProductCategoryProduct",
    # Lane D — Reference data
    "UnitOfMeasureClass",
    "UnitOfMeasure",
    "ProrationPolicy",
    # Lane E — Selling models
    "ProductSellingModel",
    # Lane F — Product core
    "Product2",
    "ProductAttributeDefinition",
    "ProductSellingModelOption",
    # Lane G — Bundle structure
    "ProductComponentGroup",
    "ProductComponentGrpOverride",
    "ProductRelatedComponent",
    # Lane H — Pricing & cost
    "PricebookEntry",
    "CostBookEntry",
    # CRM objects
    "Case",
    "Task",
    "Note",
}

_SOQL_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_SOQL_LIMIT_RE = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)


async def execute_tool(name: str, inputs: dict, sf) -> Any:
    """Execute a single tool call. sf is a SalesforceClient instance."""
    if name == "query_salesforce":
        soql = inputs.get("soql", "").strip()
        if not _SOQL_SELECT_RE.match(soql):
            return {"error": "Only SELECT queries are permitted."}
        if not _SOQL_LIMIT_RE.search(soql):
            soql += " LIMIT 50"
        try:
            result = await sf.query(soql)
            records = result.get("records", [])
            for r in records:
                r.pop("attributes", None)
            return {"totalSize": result.get("totalSize", len(records)), "records": records}
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = str(e)
            return {"error": detail}
        except Exception as e:
            return {"error": str(e)}

    if name == "create_record":
        object_name = inputs.get("object_name", "")
        if object_name not in _CREATE_ALLOWLIST:
            return {"error": f"Object '{object_name}' is not permitted. Allowed: {sorted(_CREATE_ALLOWLIST)}"}
        fields = inputs.get("fields", {})
        try:
            if object_name in _TOOLING_API_OBJECTS:
                result = await sf.tooling_create(object_name, fields)
            else:
                result = await sf.create(object_name, fields)
            return result
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = str(e)
            return {"error": detail}
        except Exception as e:
            return {"error": str(e)}

    if name == "describe_object":
        object_name = inputs.get("object_name", "")
        try:
            desc = await sf.describe_object(object_name)
            fields = [
                {
                    "name": f["name"],
                    "label": f["label"],
                    "type": f["type"],
                    "nillable": f.get("nillable", True),
                    "createable": f.get("createable", False),
                    "updateable": f.get("updateable", True),
                }
                for f in desc.get("fields", [])
            ]
            return {"object": object_name, "fieldCount": len(fields), "fields": fields}
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = str(e)
            return {"error": detail}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown tool: {name}"}
