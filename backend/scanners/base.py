import uuid
from abc import ABC, abstractmethod
from ..models.findings import Finding, ComponentType


class BaseScanner(ABC):
    component_type: ComponentType

    def _finding(
        self,
        component_name: str,
        rule_id: str,
        rule_name: str,
        severity,
        description: str,
        component_id: str = None,
        location: str = None,
        current_code: str = None,
        suggested_fix: str = None,
        impact: str = None,
        effort: str = None,
    ) -> Finding:
        return Finding(
            id=str(uuid.uuid4()),
            component_type=self.component_type,
            component_name=component_name,
            component_id=component_id,
            rule_id=rule_id,
            rule_name=rule_name,
            severity=severity,
            description=description,
            location=location,
            current_code=current_code,
            suggested_fix=suggested_fix,
            impact=impact,
            effort=effort,
        )

    @abstractmethod
    async def scan(self, components: list[dict]) -> list[Finding]:
        pass
