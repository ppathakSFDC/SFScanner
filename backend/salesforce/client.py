import asyncio
import httpx
from typing import Any


class SalesforceClient:
    def __init__(self, access_token: str, instance_url: str):
        self.access_token = access_token
        self.instance_url = instance_url.rstrip("/")
        self.api_version = "v62.0"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def query(self, soql: str) -> dict:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                f"{self.instance_url}/services/data/{self.api_version}/query",
                params={"q": soql},
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def tooling_query(self, soql: str) -> dict:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                f"{self.instance_url}/services/data/{self.api_version}/tooling/query",
                params={"q": soql},
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def tooling_get(self, path: str) -> dict:
        """GET a single Tooling API resource by relative path, e.g. 'sobjects/ApexClass/{id}'."""
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                f"{self.instance_url}/services/data/{self.api_version}/tooling/{path}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def describe_object(self, object_name: str) -> dict:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                f"{self.instance_url}/services/data/{self.api_version}/sobjects/{object_name}/describe/",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def list_sobjects(self) -> list[str]:
        """Return names of all queryable sObjects in the org."""
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                f"{self.instance_url}/services/data/{self.api_version}/sobjects/",
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return [s["name"] for s in data.get("sobjects", []) if s.get("queryable")]

    async def sobject_exists(self, name: str) -> bool:
        """Quick check whether a specific sObject is queryable."""
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                f"{self.instance_url}/services/data/{self.api_version}/sobjects/{name}/",
                headers=self.headers,
            )
            return resp.status_code == 200

    async def discover_omnistudio_objects(self) -> dict:
        """
        Check which OmniStudio / Revenue Cloud objects exist in this org.
        Returns a dict with existence + a sample row count for each candidate.
        """
        candidates = {
            # Standard OmniStudio (no namespace, Summer '22+)
            "OmniProcess":       "SELECT COUNT() FROM OmniProcess",
            "OmniDataTransform": "SELECT COUNT() FROM OmniDataTransform",
            "OmniUiCard":        "SELECT COUNT() FROM OmniUiCard",
            "OmniInteractionConfig": "SELECT COUNT() FROM OmniInteractionConfig",
            # Vlocity managed package
            "vlocity_cmt__OmniScript__c":           "SELECT COUNT() FROM vlocity_cmt__OmniScript__c",
            "vlocity_cmt__DRBundle__c":              "SELECT COUNT() FROM vlocity_cmt__DRBundle__c",
            "vlocity_cmt__IntegrationProcedure__c":  "SELECT COUNT() FROM vlocity_cmt__IntegrationProcedure__c",
            "vlocity_cmt__VlocityCard__c":           "SELECT COUNT() FROM vlocity_cmt__VlocityCard__c",
            # EPC / Revenue Cloud CPQ
            "SBQQ__PricingProcedure__c": "SELECT COUNT() FROM SBQQ__PricingProcedure__c",
            "BusinessRule":              "SELECT COUNT() FROM BusinessRule",
        }

        results = {}
        async def _check(obj_name, soql):
            try:
                r = await self.query(soql)
                results[obj_name] = {"exists": True, "count": r.get("totalSize", 0)}
            except Exception as e:
                err = str(e)
                if "400" in err or "INVALID_TYPE" in err or "sObject type" in err.lower() or "not found" in err.lower():
                    results[obj_name] = {"exists": False, "count": 0}
                else:
                    results[obj_name] = {"exists": "error", "error": err}

        await asyncio.gather(*[_check(k, v) for k, v in candidates.items()])

        # Also break down OmniProcess by Type__c if it exists
        if results.get("OmniProcess", {}).get("exists"):
            for ptype in ("OmniScript", "IntegrationProcedure", "PricingProcedure"):
                try:
                    r = await self.query(
                        f"SELECT COUNT() FROM OmniProcess WHERE Type__c = '{ptype}'"
                    )
                    results[f"OmniProcess[{ptype}]"] = {"exists": True, "count": r.get("totalSize", 0)}
                except Exception:
                    results[f"OmniProcess[{ptype}]"] = {"exists": False, "count": 0}

        return results

    async def get_limits(self) -> dict:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                f"{self.instance_url}/services/data/{self.api_version}/limits/",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_org_info(self) -> dict:
        try:
            result = await self.query(
                "SELECT Id, Name, OrganizationType, Country, TimeZoneSidKey, "
                "DefaultLocaleSidKey, LanguageLocaleKey, InstanceName FROM Organization LIMIT 1"
            )
            records = result.get("records", [])
            return records[0] if records else {}
        except Exception:
            return {}

    async def get_apex_classes(self) -> tuple[list[dict], str]:
        try:
            result = await self.tooling_query(
                "SELECT Id, Name, Body, LengthWithoutComments, ApiVersion, Status "
                "FROM ApexClass WHERE Status = 'Active' ORDER BY Name LIMIT 300"
            )
            return result.get("records", []), ""
        except Exception as e:
            return [], str(e)

    async def get_apex_triggers(self) -> tuple[list[dict], str]:
        try:
            result = await self.tooling_query(
                "SELECT Id, Name, TableEnumOrId, Body, Status, IsValid, ApiVersion "
                "FROM ApexTrigger WHERE Status = 'Active' ORDER BY TableEnumOrId, Name LIMIT 200"
            )
            return result.get("records", []), ""
        except Exception as e:
            return [], str(e)

    async def get_flows_active(self) -> tuple[list[dict], str]:
        try:
            result = await self.tooling_query(
                "SELECT Id, MasterLabel, ProcessType, Status, ApiVersion, Description "
                "FROM Flow WHERE Status = 'Active' ORDER BY MasterLabel LIMIT 200"
            )
            return result.get("records", []), ""
        except Exception as e:
            return [], str(e)

    async def get_org_limits(self) -> tuple[dict, str]:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    f"{self.instance_url}/services/data/{self.api_version}/limits/",
                    headers=self.headers,
                )
                resp.raise_for_status()
                return resp.json(), ""
        except Exception as e:
            return {}, str(e)

    async def get_custom_objects_summary(self) -> tuple[list[dict], str]:
        try:
            result = await self.tooling_query(
                "SELECT Id, DeveloperName, Label, SharingModel, ExternalSharingModel, "
                "DeploymentStatus FROM CustomObject WHERE DeploymentStatus = 'Deployed' "
                "ORDER BY DeveloperName LIMIT 300"
            )
            return result.get("records", []), ""
        except Exception as e:
            return [], str(e)

    async def _get_flow_metadata(self, flow_id: str) -> "dict | None":
        """Fetch Metadata for a single flow by ID (required by Tooling API)."""
        try:
            result = await self.tooling_query(
                f"SELECT Id, FullName, Metadata, ApiVersion, ProcessType, Status "
                f"FROM Flow WHERE Id = '{flow_id}'"
            )
            records = result.get("records", [])
            return records[0] if records else None
        except Exception:
            return None

    async def get_flows(self) -> list[dict]:
        try:
          return await self._get_flows_inner()
        except Exception:
            return []

    async def _get_flows_inner(self) -> list[dict]:
        # Bulk query to get IDs — FullName/Metadata cannot be fetched in bulk
        result = await self.tooling_query(
            "SELECT Id, MasterLabel, ApiVersion, ProcessType, Status "
            "FROM Flow WHERE Status = 'Active' ORDER BY MasterLabel LIMIT 100"
        )
        stubs = result.get("records", [])
        if not stubs:
            return []
        # Fetch metadata concurrently, cap concurrency to avoid rate limits
        sem = asyncio.Semaphore(10)
        async def _fetch(stub):
            async with sem:
                full = await self._get_flow_metadata(stub["Id"])
                if full:
                    full.setdefault("FullName", stub.get("MasterLabel", stub["Id"]))
                    return full
                stub["Metadata"] = {}
                stub["FullName"] = stub.get("MasterLabel", stub["Id"])
                return stub
        return list(await asyncio.gather(*[_fetch(s) for s in stubs]))

    async def get_omniscripts(self) -> tuple[list[dict], str]:
        """Returns (records, error_message). Tries 3 approaches in order."""
        errors = []

        # 1 — OmniScriptView (namespace-agnostic, no Id field on this view)
        try:
            result = await self.query(
                "SELECT OmniscriptName, Description, Type, SubType, Language, VersionCount, IsActive "
                "FROM OmniScriptView WHERE IsActive = TRUE ORDER BY OmniscriptName"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("Name", r.get("OmniscriptName", ""))
                r.setdefault("Type__c", r.get("Type", ""))
                r.setdefault("SubType__c", r.get("SubType", ""))
                r.setdefault("Language__c", r.get("Language", ""))
                r.setdefault("IsActive__c", r.get("IsActive", True))
            return records, ""
        except Exception as e:
            errors.append(f"OmniScriptView: {e}")

        # 2 — Standard OmniProcess (no __c suffix on standard fields)
        try:
            result = await self.query(
                "SELECT Id, Name, Type, SubType, Language, IsActive, PropertySet "
                "FROM OmniProcess WHERE Type = 'OmniScript' AND IsActive = true ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("Type__c", r.get("Type", ""))
                r.setdefault("SubType__c", r.get("SubType", ""))
                r.setdefault("Language__c", r.get("Language", ""))
                r.setdefault("IsActive__c", r.get("IsActive", True))
                r.setdefault("PropertySet__c", r.get("PropertySet", ""))
            return records, ""
        except Exception as e:
            errors.append(f"OmniProcess(standard): {e}")

        # 3 — Vlocity managed package
        try:
            result = await self.query(
                "SELECT Id, Name, vlocity_cmt__Type__c, vlocity_cmt__SubType__c, "
                "vlocity_cmt__Language__c, vlocity_cmt__IsActive__c, vlocity_cmt__PropertySet__c "
                "FROM vlocity_cmt__OmniScript__c WHERE vlocity_cmt__IsActive__c = true ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("Type__c", r.get("vlocity_cmt__Type__c", ""))
                r.setdefault("SubType__c", r.get("vlocity_cmt__SubType__c", ""))
                r.setdefault("Language__c", r.get("vlocity_cmt__Language__c", ""))
                r.setdefault("IsActive__c", r.get("vlocity_cmt__IsActive__c", True))
                r.setdefault("PropertySet__c", r.get("vlocity_cmt__PropertySet__c", ""))
            return records, ""
        except Exception as e:
            errors.append(f"vlocity_cmt__OmniScript__c: {e}")

        return [], " | ".join(errors)

    async def _enrich_omniscript_propertyset(self, records: list) -> list:
        """After fetching from OmniScriptView, get PropertySet from OmniProcess or Vlocity."""
        if not records:
            return records
        # Try standard OmniProcess PropertySet
        try:
            ids = [r["Id"] for r in records if r.get("Id")]
            if not ids:
                return records
            id_list = ", ".join(f"'{i}'" for i in ids[:200])
            result = await self.query(
                f"SELECT Id, PropertySet FROM OmniProcess WHERE Id IN ({id_list})"
            )
            ps_map = {r["Id"]: r.get("PropertySet", "") for r in result.get("records", [])}
            for r in records:
                r["PropertySet__c"] = ps_map.get(r["Id"], "")
        except Exception:
            pass
        return records

    async def get_dataraptors(self) -> tuple[list[dict], str]:
        """Returns (records, error_message). Tries 3 approaches in order."""
        errors = []

        # 1 — OmniDataMapperView (namespace-agnostic, no Id field)
        try:
            result = await self.query(
                "SELECT DataMapperName, Description, Type, VersionCount "
                "FROM OmniDataMapperView ORDER BY DataMapperName"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("Name", r.get("DataMapperName", ""))
                r.setdefault("InterfaceType__c", r.get("Type", ""))
            return records, ""
        except Exception as e:
            errors.append(f"OmniDataMapperView: {e}")

        # 2 — Standard OmniDataTransform (correct field names)
        try:
            result = await self.query(
                "SELECT Id, Name, Type, PropertySet FROM OmniDataTransform ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("InterfaceType__c", r.get("Type", ""))
                r.setdefault("PropertySet__c", r.get("PropertySet", ""))
            return records, ""
        except Exception as e:
            errors.append(f"OmniDataTransform(standard): {e}")

        # 3 — Vlocity
        try:
            result = await self.query(
                "SELECT Id, Name, vlocity_cmt__InterfaceType__c, vlocity_cmt__PropertySet__c "
                "FROM vlocity_cmt__DRBundle__c ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("InterfaceType__c", r.get("vlocity_cmt__InterfaceType__c", ""))
                r.setdefault("PropertySet__c", r.get("vlocity_cmt__PropertySet__c", ""))
            return records, ""
        except Exception as e:
            errors.append(f"vlocity_cmt__DRBundle__c: {e}")

        return [], " | ".join(errors)

    async def get_integration_procedures(self) -> tuple[list[dict], str]:
        """Returns (records, error_message). Tries 3 approaches in order."""
        errors = []

        # 1 — OmniIntegrationProcdView (namespace-agnostic, no Id field)
        try:
            result = await self.query(
                "SELECT IntegrationProcedureName, Description, Type, SubType, VersionCount, IsActive "
                "FROM OmniIntegrationProcdView WHERE IsActive = TRUE ORDER BY IntegrationProcedureName"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("Name", r.get("IntegrationProcedureName", ""))
                r.setdefault("IsActive__c", r.get("IsActive", True))
            return records, ""
        except Exception as e:
            errors.append(f"OmniIntegrationProcdView: {e}")

        # 2 — Standard OmniProcess (correct field names)
        try:
            result = await self.query(
                "SELECT Id, Name, Type, SubType, IsActive, PropertySet "
                "FROM OmniProcess WHERE Type = 'IntegrationProcedure' AND IsActive = true ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("IsActive__c", r.get("IsActive", True))
                r.setdefault("PropertySet__c", r.get("PropertySet", ""))
            return records, ""
        except Exception as e:
            errors.append(f"OmniProcess(IP standard): {e}")

        # 3 — Vlocity
        try:
            result = await self.query(
                "SELECT Id, Name, vlocity_cmt__IsActive__c, vlocity_cmt__PropertySet__c "
                "FROM vlocity_cmt__IntegrationProcedure__c WHERE vlocity_cmt__IsActive__c = true ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("IsActive__c", r.get("vlocity_cmt__IsActive__c", True))
                r.setdefault("PropertySet__c", r.get("vlocity_cmt__PropertySet__c", ""))
            return records, ""
        except Exception as e:
            errors.append(f"vlocity_cmt__IntegrationProcedure__c: {e}")

        return [], " | ".join(errors)

    async def _enrich_ip_propertyset(self, records: list) -> list:
        if not records:
            return records
        try:
            ids = [r["Id"] for r in records if r.get("Id")]
            if not ids:
                return records
            id_list = ", ".join(f"'{i}'" for i in ids[:200])
            result = await self.query(
                f"SELECT Id, PropertySet FROM OmniProcess WHERE Id IN ({id_list})"
            )
            ps_map = {r["Id"]: r.get("PropertySet", "") for r in result.get("records", [])}
            for r in records:
                r["PropertySet__c"] = ps_map.get(r["Id"], "")
        except Exception:
            pass
        return records

    async def get_flexcards(self) -> tuple[list[dict], str]:
        """Returns (records, error_message). Tries 3 approaches in order."""
        errors = []

        # 1 — OmniFlexCardView (namespace-agnostic, no Id field)
        try:
            result = await self.query(
                "SELECT FlexcardName, Description, Author, VersionCount "
                "FROM OmniFlexCardView ORDER BY FlexcardName"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("Name", r.get("FlexcardName", ""))
            return records, ""
        except Exception as e:
            errors.append(f"OmniFlexCardView: {e}")

        # 2 — Standard OmniUiCard
        try:
            result = await self.query(
                "SELECT Id, Name, IsActive, PropertySet FROM OmniUiCard WHERE IsActive = true ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("PropertySet__c", r.get("PropertySet", ""))
            return records, ""
        except Exception as e:
            errors.append(f"OmniUiCard(standard): {e}")

        # 3 — Vlocity
        try:
            result = await self.query(
                "SELECT Id, Name, vlocity_cmt__IsActive__c "
                "FROM vlocity_cmt__VlocityCard__c WHERE vlocity_cmt__IsActive__c = true ORDER BY Name"
            )
            return result.get("records", []), ""
        except Exception as e:
            errors.append(f"vlocity_cmt__VlocityCard__c: {e}")

        return [], " | ".join(errors)

    async def get_pricing_procedures(self) -> tuple[list[dict], str]:
        errors = []
        # Standard OmniProcess (correct field names)
        try:
            result = await self.query(
                "SELECT Id, Name, IsActive, PropertySet "
                "FROM OmniProcess WHERE Type = 'PricingProcedure' AND IsActive = true"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("IsActive__c", r.get("IsActive", True))
                r.setdefault("PropertySet__c", r.get("PropertySet", ""))
            return records, ""
        except Exception as e:
            errors.append(f"OmniProcess(PP): {e}")
        try:
            result = await self.query(
                "SELECT Id, Name, SBQQ__Active__c FROM SBQQ__PricingProcedure__c"
            )
            return result.get("records", []), ""
        except Exception as e:
            errors.append(f"SBQQ__PricingProcedure__c: {e}")
        return [], " | ".join(errors)

    async def get_business_rules(self) -> tuple[list[dict], str]:
        """Fetch BRE components. Tries Revenue Cloud native, vlocity legacy, then ExpressionSetDefinition."""
        errors = []
        # Revenue Cloud 2.0+ native BRE
        try:
            result = await self.query(
                "SELECT Id, Name, IsActive, PropertySet__c FROM BusinessRule ORDER BY Name LIMIT 500"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("_bre_type", "BusinessRule")
            return records, ""
        except Exception as e:
            errors.append(f"BusinessRule: {e}")
        # Legacy vlocity BRE
        try:
            result = await self.query(
                "SELECT Id, Name, vlocity_cmt__IsActive__c, vlocity_cmt__PropertySet__c "
                "FROM vlocity_cmt__BusinessRule__c ORDER BY Name LIMIT 500"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("_bre_type", "vlocity_cmt__BusinessRule__c")
            return records, ""
        except Exception as e:
            errors.append(f"vlocity_cmt__BusinessRule__c: {e}")
        # ExpressionSetDefinition (Revenue Cloud / Decision Engine)
        try:
            result = await self.query(
                "SELECT Id, Name, MasterLabel, Status, Type FROM ExpressionSetDefinition ORDER BY Name LIMIT 500"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("_bre_type", "ExpressionSetDefinition")
                # Normalise to common field names consumed by analyzers
                if "MasterLabel" in r and "Name" not in r:
                    r["Name"] = r["MasterLabel"]
                is_active = r.get("Status", "") in ("Active", "Draft")
                r.setdefault("IsActive", is_active)
            return records, ""
        except Exception as e:
            errors.append(f"ExpressionSetDefinition: {e}")
        return [], " | ".join(errors)

    async def get_cml_rules(self) -> tuple[list[dict], str]:
        """Fetch CML (Constraint Model Language) rules. Tries multiple sObject names."""
        errors = []
        for soql, label in [
            ("SELECT Id, Name FROM ConstraintModelDefinition ORDER BY Name", "ConstraintModelDefinition"),
            ("SELECT Id, Name, vlocity_cmt__Active__c FROM vlocity_cmt__CMLRule__c ORDER BY Name", "vlocity_cmt__CMLRule__c"),
            ("SELECT Id, Name FROM ConstraintModelDef__c ORDER BY Name", "ConstraintModelDef__c"),
        ]:
            try:
                result = await self.query(soql)
                return result.get("records", []), ""
            except Exception as e:
                errors.append(f"{label}: {e}")
        return [], " | ".join(errors)

    async def get_data_mappers(self) -> tuple[list[dict], str]:
        """Fetch OmniStudio Data Mapper components (Type=DataMapping)."""
        errors = []
        try:
            result = await self.query(
                "SELECT DataMapperName, Description, Type, VersionCount "
                "FROM OmniDataMapperView WHERE Type = 'DataMapping' ORDER BY DataMapperName"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("Name", r.get("DataMapperName", ""))
                r.setdefault("sub_type", "DataMapping")
            return records, ""
        except Exception as e:
            errors.append(f"OmniDataMapperView(DataMapping): {e}")
        try:
            result = await self.query(
                "SELECT Id, Name, Type FROM OmniDataTransform WHERE Type = 'DataMapping' ORDER BY Name"
            )
            records = result.get("records", [])
            for r in records:
                r.setdefault("sub_type", "DataMapping")
            return records, ""
        except Exception as e:
            errors.append(f"OmniDataTransform(DataMapping): {e}")
        return [], " | ".join(errors)

    async def get_profiles_and_permsets(self) -> tuple[list[dict], "str | None"]:
        perm_fields = [
            "PermissionsViewAllData", "PermissionsModifyAllData", "PermissionsManageUsers",
            "PermissionsAuthorApex", "PermissionsInstallPackaging",
            "PermissionsApiEnabled", "PermissionsBulkApiHardDelete", "PermissionsManageEncryptionKeys",
        ]
        fields_str = ", ".join(perm_fields)
        results = []
        error = None
        try:
            r = await self.query(
                f"SELECT Id, Name, {fields_str} FROM Profile WHERE IsCustom = true LIMIT 200"
            )
            for rec in r.get("records", []):
                rec["_type"] = "Profile"
                results.append(rec)
            r2 = await self.query(
                f"SELECT Id, Name, Label, {fields_str} FROM PermissionSet WHERE IsOwnedByProfile = false LIMIT 200"
            )
            for rec in r2.get("records", []):
                rec["_type"] = "PermissionSet"
                results.append(rec)
        except Exception as e:
            error = str(e)
        return results, error

    async def get_security_settings(self) -> dict:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    f"{self.instance_url}/services/data/{self.api_version}/settings/Security",
                    headers=self.headers,
                )
                return resp.json() if resp.status_code == 200 else {}
            except Exception:
                return {}

    async def get_connected_apps(self) -> list[dict]:
        try:
            result = await self.tooling_query(
                "SELECT Id, Name, OptionsAllowAllProfiles FROM ConnectedApplication LIMIT 200"
            )
            return result.get("records", []) if isinstance(result, dict) else []
        except Exception:
            return []

    async def get_entity_sharing_models(self) -> list[dict]:
        try:
            result = await self.query(
                "SELECT QualifiedApiName, InternalSharingModel, ExternalSharingModel "
                "FROM EntityDefinition WHERE IsCustomizable = true AND QualifiedApiName LIKE '%__c' LIMIT 500"
            )
            return result.get("records", []) if isinstance(result, dict) else []
        except Exception:
            return []

    async def get_custom_fields_with_pii(self) -> list[dict]:
        try:
            result = await self.tooling_query(
                "SELECT QualifiedApiName, Label, DataType, IsEncrypted, "
                "EntityDefinitionId, EntityDefinition.QualifiedApiName "
                "FROM CustomField WHERE ManageableState = 'unmanaged' LIMIT 2000"
            )
            return result.get("records", []) if isinstance(result, dict) else []
        except Exception:
            return []

    async def get_tracked_fields(self) -> list[dict]:
        try:
            result = await self.query(
                "SELECT ParentId, FieldName FROM FieldHistoryRetention LIMIT 2000"
            )
            return result.get("records", []) if isinstance(result, dict) else []
        except Exception:
            return []

    async def bulk_update(self, object_name: str, records: list[dict]) -> list[dict]:
        """PATCH up to 200 records via the sObject Collections API."""
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.patch(
                f"{self.instance_url}/services/data/{self.api_version}/composite/sobjects",
                headers=self.headers,
                json={"allOrNone": False, "records": [{"attributes": {"type": object_name}, **r} for r in records]},
            )
            resp.raise_for_status()
            return resp.json()

    async def bulk_delete(self, object_name: str, record_ids: list[str]) -> list[dict]:
        """DELETE up to 200 records via the sObject Collections API."""
        ids_param = ",".join(record_ids)
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.delete(
                f"{self.instance_url}/services/data/{self.api_version}/composite/sobjects",
                headers=self.headers,
                params={"ids": ids_param, "allOrNone": "false"},
            )
            resp.raise_for_status()
            return resp.json()
