from .models.findings import ScanResult

_scans: dict[str, ScanResult] = {}
_scan_progress: dict[str, dict] = {}
