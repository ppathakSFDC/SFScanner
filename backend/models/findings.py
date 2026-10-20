from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ComponentType(str, Enum):
    OMNISCRIPT = "OmniScript"
    FLOW = "Flow"
    APEX = "Apex"
    SOQL = "SOQL"
    DATARAPTOR = "DataRaptor"
    INTEGRATION_PROCEDURE = "Integration Procedure"
    PRICING_PROCEDURE = "Pricing Procedure"
    BUSINESS_RULES = "Business Rules"
    PERMISSION = "Permission"
    SECURITY = "Security"
    COMPLIANCE = "Compliance"


class Finding(BaseModel):
    id: str
    component_type: ComponentType
    component_name: str
    component_id: Optional[str] = None
    rule_id: str
    rule_name: str
    severity: Severity
    description: str
    location: Optional[str] = None
    current_code: Optional[str] = None
    suggested_fix: Optional[str] = None
    ai_explanation: Optional[str] = None
    ai_fix_diff: Optional[str] = None
    impact: Optional[str] = None
    effort: Optional[str] = None  # low / medium / high


class ScanResult(BaseModel):
    org_id: str
    org_name: str
    scan_id: str
    started_at: str
    completed_at: Optional[str] = None
    total_components: int = 0
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    findings: list[Finding] = []
    component_summary: dict = {}
    scanner_timing: dict = {}
    scan_duration_ms: Optional[int] = None
    executive_summary: str = ""
    recommendations: list[dict] = []
    health_scores: dict = {}
    compliance_scores: dict = {}


class ScanProgress(BaseModel):
    scan_id: str
    status: str  # running / completed / failed
    current_component: Optional[str] = None
    progress_pct: int = 0
    message: Optional[str] = None
