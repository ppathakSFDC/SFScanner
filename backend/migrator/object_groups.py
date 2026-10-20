"""
Predefined object groups for migration, ordered by dependency tier.
Each object specifies its direct parents so the engine can do a
topological sort at migration time.

Virtual objects (OmniStudio, CML, Pricing Procedures) are handled via
the SF client's specialised methods rather than generic SOQL/Bulk API.
"""

OBJECT_GROUPS = [
    {
        "key": "standard_crm",
        "label": "Standard CRM",
        "icon": "🏢",
        "description": "Core CRM records — Accounts, Contacts, Orders",
        "objects": [
            {"name": "Account",          "label": "Accounts",           "deps": [],                             "tier": 0},
            {"name": "Contact",          "label": "Contacts",           "deps": ["Account"],                    "tier": 1},
            {"name": "Opportunity",      "label": "Opportunities",      "deps": ["Account"],                    "tier": 1},
            {"name": "OpportunityLineItem", "label": "Opp Line Items",  "deps": ["Opportunity", "PricebookEntry"], "tier": 3},
            {"name": "Quote",            "label": "Quotes",             "deps": ["Opportunity"],                "tier": 2},
            {"name": "QuoteLineItem",    "label": "Quote Line Items",   "deps": ["Quote", "PricebookEntry"],    "tier": 3},
            {"name": "Order",            "label": "Orders",             "deps": ["Account"],                    "tier": 2},
            {"name": "OrderItem",        "label": "Order Items",        "deps": ["Order", "PricebookEntry"],    "tier": 3},
        ],
    },
    {
        "key": "revenue_product_bundle",
        "label": "Revenue Product Bundle",
        "icon": "🛒",
        "description": "Complete Revenue Cloud product setup — UoM, attributes, classifications, pricing, selling models, and catalogs",
        "probe_object": "ProductCatalog",
        "primary_object": "Product2",
        "objects": [
            # ── Tier 0 — no dependencies ─────────────────────────────────────
            {"name": "UnitOfMeasureClass",          "label": "Unit of Measure Classes",         "deps": [],                                                           "tier": 0},
            {"name": "AttributeCategory",           "label": "Attribute Categories",            "deps": [],                                                           "tier": 0},
            {"name": "AttributePicklist",           "label": "Attribute Picklists",             "deps": ["UnitOfMeasure"],                                           "tier": 2},
            {"name": "AttributeDefinition",         "label": "Attribute Definitions",           "deps": ["AttributePicklist", "UnitOfMeasure"],                      "tier": 3},
            {"name": "ProductSpecificationType",    "label": "Product Specification Types",     "deps": [],                                                           "tier": 0},
            {"name": "CostBook",                    "label": "Cost Books",                      "deps": [],                                                           "tier": 0},
            {"name": "Pricebook2",                  "label": "Price Books",                     "deps": [],                                                           "tier": 0},
            {"name": "ProrationPolicy",             "label": "Proration Policies",              "deps": [],                                                           "tier": 0},
            {"name": "ProductSellingModel",         "label": "Selling Models",                  "deps": [],                                                           "tier": 0},
            {"name": "ProductCatalog",              "label": "Product Catalogs",                "deps": [],                                                           "tier": 0},
            {"name": "Product2",                    "label": "Products",                        "deps": ["ProductClassification", "UnitOfMeasure"],                  "tier": 2},
            # ── Tier 1 ───────────────────────────────────────────────────────
            {"name": "UnitOfMeasure",               "label": "Units of Measure",                "deps": ["UnitOfMeasureClass"],                                       "tier": 1},
            {"name": "AttributePicklistValue",      "label": "Attribute Picklist Values",       "deps": ["AttributePicklist"],                                        "tier": 3},
            {"name": "AttributeCategoryAttribute",  "label": "Attribute Category Attributes",   "deps": ["AttributeCategory", "AttributeDefinition"],                 "tier": 1},
            {"name": "ProductSpecificationRecType", "label": "Product Specification Rec Types", "deps": ["ProductSpecificationType"],                                  "tier": 1},
            {"name": "CostBookEntry",               "label": "Cost Book Entries",               "deps": ["CostBook", "Product2"],                                     "tier": 1},
            {"name": "ProductSellingModelOption",   "label": "Selling Model Options",           "deps": ["ProductSellingModel", "Product2"],                          "tier": 1},
            {"name": "PricebookEntry",              "label": "Pricebook Entries",               "deps": ["Pricebook2", "Product2"],                                   "tier": 1},
            {"name": "ProductCategory",             "label": "Product Categories",              "deps": ["ProductCatalog"],                                           "tier": 1},
            {"name": "ProductAttributeDefinition",  "label": "Product Attribute Definitions",   "deps": ["Product2", "AttributeDefinition"],                          "tier": 1},
            # ── Tier 2 ───────────────────────────────────────────────────────
            {"name": "AttrPicklistExcludedValue",   "label": "Attr Picklist Excluded Values",   "deps": ["AttributePicklistValue", "ProductAttributeDefinition", "ProductClassificationAttr"], "tier": 2},
            {"name": "ProductClassification",       "label": "Product Classifications",         "deps": ["AttributeDefinition"],                                    "tier": 1},
            {"name": "Product2DataTranslation",     "label": "Product Data Translations",       "deps": ["Product2"],                                                 "tier": 2},
            {"name": "ProductCategoryDataTranslation","label":"Product Category Translations",  "deps": ["ProductCategory"],                                          "tier": 2},
            {"name": "ProductCategoryProduct",      "label": "Category → Product Links",        "deps": ["ProductCategory", "Product2"],                             "tier": 2},
            {"name": "ProductComponentGroup",       "label": "Product Component Groups",        "deps": ["Product2"],                                                 "tier": 2},
            # ── Tier 3 ───────────────────────────────────────────────────────
            {"name": "ProductClassificationAttr",   "label": "Product Classification Attrs",    "deps": ["ProductClassification", "AttributeDefinition"],             "tier": 3},
            {"name": "ProductComponentGrpOverride", "label": "Product Component Grp Overrides", "deps": ["ProductComponentGroup"],                                    "tier": 3},
            {"name": "ProductRelationshipType",     "label": "Product Relationship Types",      "deps": [],                                                           "tier": 0},
            {"name": "ProductRelatedComponent",     "label": "Product Related Components",      "deps": ["ProductComponentGroup", "ProductRelationshipType", "Product2", "ProductClassification", "ProductSellingModel", "UnitOfMeasure"], "tier": 3},
            {"name": "ProductRampSegment",          "label": "Product Ramp Segments",           "deps": ["Product2", "ProductSellingModel"], "tier": 3},
        ],
    },
    {
        "key": "rca_product_catalog",
        "label": "Revenue Cloud — Product Catalog",
        "icon": "📦",
        "description": "Product catalogs, categories, attribute sets, classifications, pricing, and selling models (RCA PCM)",
        "probe_object": "ProductCatalog",
        "primary_object": "Product2",
        "objects": [
            # ── Tier 0 — no dependencies ─────────────────────────────────────
            {"name": "UnitOfMeasureClass",          "label": "Unit of Measure Classes",         "deps": [],                                                           "tier": 0},
            {"name": "AttributeCategory",           "label": "Attribute Categories",            "deps": [],                                                           "tier": 0},
            {"name": "AttributePicklist",           "label": "Attribute Picklists",             "deps": ["UnitOfMeasure"],                                           "tier": 2},
            {"name": "AttributeDefinition",         "label": "Attribute Definitions",           "deps": ["AttributePicklist", "UnitOfMeasure"],                      "tier": 3},
            {"name": "ProductSpecificationType",    "label": "Product Specification Types",     "deps": [],                                                           "tier": 0},
            {"name": "CostBook",                    "label": "Cost Books",                      "deps": [],                                                           "tier": 0},
            {"name": "Pricebook2",                  "label": "Price Books",                     "deps": [],                                                           "tier": 0},
            {"name": "ProrationPolicy",             "label": "Proration Policies",              "deps": [],                                                           "tier": 0},
            {"name": "ProductSellingModel",         "label": "Selling Models",                  "deps": [],                                                           "tier": 0},
            {"name": "ProductCatalog",              "label": "Product Catalogs",                "deps": [],                                                           "tier": 0},
            {"name": "Product2",                    "label": "Products",                        "deps": ["ProductClassification", "UnitOfMeasure"],                  "tier": 2},
            # ── Tier 1 ───────────────────────────────────────────────────────
            {"name": "UnitOfMeasure",               "label": "Units of Measure",                "deps": ["UnitOfMeasureClass"],                                       "tier": 1},
            {"name": "AttributePicklistValue",      "label": "Attribute Picklist Values",       "deps": ["AttributePicklist"],                                        "tier": 3},
            {"name": "AttributeCategoryAttribute",  "label": "Attribute Category Attributes",   "deps": ["AttributeCategory", "AttributeDefinition"],                 "tier": 1},
            {"name": "ProductSpecificationRecType", "label": "Product Specification Rec Types", "deps": ["ProductSpecificationType"],                                  "tier": 1},
            {"name": "CostBookEntry",               "label": "Cost Book Entries",               "deps": ["CostBook", "Product2"],                                     "tier": 1},
            {"name": "ProductSellingModelOption",   "label": "Selling Model Options",           "deps": ["ProductSellingModel", "Product2"],                          "tier": 1},
            {"name": "PricebookEntry",              "label": "Pricebook Entries",               "deps": ["Pricebook2", "Product2"],                                   "tier": 1},
            {"name": "ProductCategory",             "label": "Product Categories",              "deps": ["ProductCatalog"],                                           "tier": 1},
            {"name": "ProductAttributeDefinition",  "label": "Product Attribute Definitions",   "deps": ["Product2", "AttributeDefinition"],                          "tier": 1},
            # ── Tier 2 ───────────────────────────────────────────────────────
            {"name": "AttrPicklistExcludedValue",   "label": "Attr Picklist Excluded Values",   "deps": ["AttributePicklistValue", "ProductAttributeDefinition", "ProductClassificationAttr"], "tier": 2},
            {"name": "ProductClassification",       "label": "Product Classifications",         "deps": ["AttributeDefinition"],                                    "tier": 1},
            {"name": "Product2DataTranslation",     "label": "Product Data Translations",       "deps": ["Product2"],                                                 "tier": 2},
            {"name": "ProductCategoryDataTranslation","label":"Product Category Translations",  "deps": ["ProductCategory"],                                          "tier": 2},
            {"name": "ProductCategoryProduct",      "label": "Category → Product Links",        "deps": ["ProductCategory", "Product2"],                             "tier": 2},
            {"name": "ProductComponentGroup",       "label": "Product Component Groups",        "deps": ["Product2"],                                                 "tier": 2},
            # ── Tier 3 ───────────────────────────────────────────────────────
            {"name": "ProductClassificationAttr",   "label": "Product Classification Attrs",    "deps": ["ProductClassification", "AttributeDefinition"],             "tier": 3},
            {"name": "ProductComponentGrpOverride", "label": "Product Component Grp Overrides", "deps": ["ProductComponentGroup"],                                    "tier": 3},
            {"name": "ProductRelationshipType",     "label": "Product Relationship Types",      "deps": [],                                                           "tier": 0},
            {"name": "ProductRelatedComponent",     "label": "Product Related Components",      "deps": ["ProductComponentGroup", "ProductRelationshipType", "Product2", "ProductClassification", "ProductSellingModel", "UnitOfMeasure"], "tier": 3},
            {"name": "ProductRampSegment",          "label": "Product Ramp Segments",           "deps": ["Product2", "ProductSellingModel"], "tier": 3},
        ],
    },
    {
        "key": "rca_selling_models",
        "label": "Revenue Cloud — Selling Models",
        "icon": "💼",
        "description": "Selling models and term-based product options",
        "probe_object": "ProductSellingModel",
        "objects": [
            {"name": "ProductSellingModel",        "label": "Selling Models",                 "deps": [],                                               "tier": 0},
            {"name": "ProductSellingModelOption",  "label": "Selling Model Options",          "deps": ["ProductSellingModel", "Product2"],              "tier": 1},
        ],
    },
    {
        "key": "rca_pricing",
        "label": "Revenue Cloud — Pricing",
        "icon": "💰",
        "description": "Price adjustment schedules, tiers, and price lists",
        "probe_object": "PriceAdjustmentSchedule",
        "objects": [
            {"name": "PriceAdjustmentSchedule",    "label": "Price Adjustment Schedules",     "deps": [],                                               "tier": 0},
            {"name": "PriceAdjustmentTier",        "label": "Price Adjustment Tiers",         "deps": ["PriceAdjustmentSchedule"],                      "tier": 1},
        ],
    },
    {
        "key": "cml_expression_sets",
        "label": "Constraint Model Language (CML) — Expression Sets",
        "icon": "🔗",
        "description": "ExpressionSets power CML rules: pricing logic, eligibility, promotions",
        "probe_object": "ExpressionSetDefinition",
        "primary_object": "ExpressionSetDefinition",
        "objects": [
            # Tier 0 — root definition objects
            {"name": "ExpressionSetDefinition",                    "label": "Expression Set Definitions",               "deps": [],                                                       "tier": 0},
            # Tier 1 — depend on ExpressionSetDefinition
            {"name": "ExpressionSet",                              "label": "Expression Sets",                          "deps": ["ExpressionSetDefinition"],                              "tier": 1},
            {"name": "ExpressionSetDefinitionContextDefinition",   "label": "Expression Set Def Context Definitions",   "deps": ["ExpressionSetDefinition"],                              "tier": 1},
            {"name": "ExpressionSetConstraintObj",                 "label": "Expression Set Constraint Objects",        "deps": ["ExpressionSetDefinition"],                              "tier": 1},
            {"name": "ExpressionSetDefinitionVersion",             "label": "Expression Set Definition Versions",       "deps": ["ExpressionSetDefinition"],                              "tier": 1},
            {"name": "ExpressionSetObjectAlias",                   "label": "Expression Set Object Aliases",            "deps": ["ExpressionSet"],                                        "tier": 1},
            {"name": "ExpressionSetMessageToken",                  "label": "Expression Set Message Tokens",            "deps": ["ExpressionSet"],                                        "tier": 1},
            # Tier 2 — depend on both ExpressionSet and ExpressionSetDefinitionVersion
            {"name": "ExpressionSetVersion",                       "label": "Expression Set Versions",                  "deps": ["ExpressionSet", "ExpressionSetDefinitionVersion"],      "tier": 2},
        ],
    },
    {
        "key": "omnistudio_dataraptor",
        "label": "OmniStudio — Data Raptor",
        "icon": "🗂️",
        "description": "DataRaptor transform definitions and their field-mapping items",
        "probe_object": "OmniDataTransform",
        "primary_object": "OmniDataTransform",
        "objects": [
            {"name": "OmniDataTransform",     "label": "Data Transforms",       "deps": [],                    "tier": 0},
            {"name": "OmniDataTransformItem", "label": "Data Transform Items",   "deps": ["OmniDataTransform"], "tier": 1},
        ],
    },
    {
        "key": "omnistudio_integration_procedure",
        "label": "OmniStudio — Integration Procedure",
        "icon": "⚙️",
        "description": "Integration Procedure definitions and their child process elements",
        "probe_object": "OmniProcess",
        "primary_object": "OmniProcess",
        "objects": [
            {"name": "OmniProcess",        "label": "Integration Procedures",          "deps": [],              "tier": 0},
            {"name": "OmniProcessElement", "label": "Integration Procedure Elements",  "deps": ["OmniProcess"], "tier": 1},
        ],
    },
    {
        "key": "cml_business_rules",
        "label": "Constraint Model Language (CML) — Business Rules",
        "icon": "📐",
        "description": "BusinessRule objects: conditional constraints, eligibility, pricing guards",
        "probe_object": "BusinessRule",
        "objects": [
            {"name": "BusinessRule",               "label": "Business Rules",                 "deps": [],                                               "tier": 0},
            {"name": "BusinessRuleCondition",      "label": "Business Rule Conditions",       "deps": ["BusinessRule"],                                 "tier": 1},
        ],
    },
    {
        "key": "omnistudio_pricing",
        "label": "OmniStudio — Pricing Procedures",
        "icon": "⚙️",
        "description": "OmniProcess Pricing Procedures with embedded CML JSON formulas",
        "virtual": True,
        "probe_key": "OmniProcess[PricingProcedure]",
        "objects": [
            {
                "name": "PricingProcedure",
                "label": "Pricing Procedures (OmniProcess)",
                "deps": [],
                "tier": 0,
                "virtual": True,
                "note": "Stored as OmniProcess WHERE Type='PricingProcedure'. Migrated via DataPack / metadata API.",
            },
        ],
    },
    {
        "key": "omnistudio_core",
        "label": "OmniStudio — Core Components",
        "icon": "🤖",
        "description": "OmniScripts, DataRaptors, Integration Procedures, FlexCards",
        "virtual": True,
        "probe_key": "OmniProcess",
        "objects": [
            {"name": "OmniScript",            "label": "OmniScripts",              "deps": [],               "tier": 0, "virtual": True},
            {"name": "DataRaptor",            "label": "DataRaptors",              "deps": [],               "tier": 0, "virtual": True},
            {"name": "IntegrationProcedure",  "label": "Integration Procedures",   "deps": [],               "tier": 0, "virtual": True},
            {"name": "FlexCard",              "label": "FlexCards",                "deps": [],               "tier": 0, "virtual": True},
        ],
    },
    {
        "key": "vlocity_pricing",
        "label": "Vlocity Revenue Cloud — Pricing & CML",
        "icon": "⚡",
        "description": "Vlocity-namespaced Pricing Procedures with CML, constraint rules, attribute models",
        "probe_object": "vlocity_cmt__PricingProcedure__c",
        "objects": [
            {"name": "vlocity_cmt__PricingProcedure__c",   "label": "Pricing Procedures (Vlocity)",     "deps": [],                                             "tier": 0},
            {"name": "vlocity_cmt__ContextDefinition__c",  "label": "Context Definitions",              "deps": [],                                             "tier": 0},
            {"name": "vlocity_cmt__ContextMapping__c",     "label": "Context Mappings",                 "deps": ["vlocity_cmt__ContextDefinition__c"],          "tier": 1},
            {"name": "vlocity_cmt__AttributeCategory__c",  "label": "Attribute Categories",             "deps": [],                                             "tier": 0},
            {"name": "vlocity_cmt__ObjectClass__c",        "label": "Object Classes (Attribute Model)", "deps": [],                                             "tier": 0},
            {"name": "vlocity_cmt__ObjectFunctionLink__c", "label": "Object Function Links",            "deps": ["vlocity_cmt__ObjectClass__c"],                "tier": 1},
        ],
    },
]

# Fast lookup: object name → group key
OBJECT_TO_GROUP = {
    obj["name"]: grp["key"]
    for grp in OBJECT_GROUPS
    for obj in grp["objects"]
}

# Fast lookup: object name → deps list
OBJECT_DEPS = {
    obj["name"]: obj["deps"]
    for grp in OBJECT_GROUPS
    for obj in grp["objects"]
}

PRODUCT_BUNDLE_OBJECTS = frozenset(obj['name'] for obj in OBJECT_GROUPS[1]['objects'])
