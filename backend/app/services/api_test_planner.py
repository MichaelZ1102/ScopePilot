"""API Test Plan service - parse OpenAPI specs and generate AI test scenarios.

Phase 3: In-memory store persisted to local JSON via SqliteStore.
"""
import json
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

import httpx
from pydantic import BaseModel, Field

from ..database import SqliteStore

logger = logging.getLogger(__name__)


class ApiSpecStore(SqliteStore):
    _entity_name = "api_specs"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class TestPlanStore(SqliteStore):
    _entity_name = "test_plans"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class ApiImpactStore(SqliteStore):
    _entity_name = "api_impacts"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_api_specs = ApiSpecStore._store
_test_plans = TestPlanStore._store
_api_impacts = ApiImpactStore._store


class ApiTestPlanError(Exception):
    """Base exception for API test plan service."""


# ── Internal schemas ──────────────────────────────────────────────────────

class Endpoint(BaseModel):
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH, etc.
    summary: str = ""
    description: str = ""
    parameters: list[dict] = Field(default_factory=list)
    request_body: Optional[dict] = None
    responses: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    security: list[dict] = Field(default_factory=list)


class TestScenario(BaseModel):
    endpoint: str
    method: str
    scenario_name: str
    description: str
    test_input: dict = Field(default_factory=dict)
    expected_status: int = 200
    expected_behavior: str = ""
    test_type: str = "positive"  # positive, negative, edge, security, performance


class TestPlan(BaseModel):
    spec_id: int
    title: str
    base_url: str = ""
    endpoints_analyzed: int = 0
    scenarios: list[dict] = Field(default_factory=list)
    coverage_summary: dict = Field(default_factory=dict)
    created_at: str = ""


class ApiTestPlannerService:
    """Service for parsing OpenAPI specs and generating AI test plans."""

    # ── Spec Management ──────────────────────────────────────────────────

    @classmethod
    async def create_spec_from_url(
        cls,
        url: str,
        name: str,
        workspace_id: int,
        project_id: Optional[int] = None,
        service_name: str = "",
    ) -> dict:
        """Fetch and parse an OpenAPI spec from a URL."""
        try:
            resp = httpx.get(url, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            raw = resp.text
        except Exception as e:
            raise ApiTestPlanError(f"Failed to fetch spec from {url}: {e}")

        return await cls._store_spec(
            raw,
            url,
            name,
            workspace_id,
            project_id=project_id,
            service_name=service_name,
        )

    @classmethod
    async def create_spec_from_content(
        cls,
        content: str,
        name: str,
        source: str,
        workspace_id: int,
        project_id: Optional[int] = None,
        service_name: str = "",
    ) -> dict:
        """Parse an inline OpenAPI spec."""
        return await cls._store_spec(
            content,
            source,
            name,
            workspace_id,
            project_id=project_id,
            service_name=service_name,
        )

    @classmethod
    async def _store_spec(
        cls,
        raw: str,
        source: str,
        name: str,
        workspace_id: int,
        project_id: Optional[int] = None,
        service_name: str = "",
    ) -> dict:
        # Parse JSON or YAML
        parsed = cls._parse_openapi(raw)
        if not parsed or not isinstance(parsed, dict):
            raise ApiTestPlanError("Invalid OpenAPI spec: could not parse JSON/YAML")

        # Extract endpoints
        endpoints = cls._extract_endpoints(parsed)
        previous = max(
            (
                item for item in _api_specs.values()
                if item.get("workspace_id") == workspace_id
                and item.get("project_id") == project_id
                and (
                    (service_name and item.get("service_name") == service_name)
                    or (not service_name and item.get("name") == name)
                )
            ),
            key=lambda item: item.get("created_at", ""),
            default=None,
        )
        current_endpoint_map = {
            (endpoint.method, endpoint.path): endpoint.model_dump()
            for endpoint in endpoints
        }
        previous_endpoint_map = {
            (item.get("method"), item.get("path")): item
            for item in (previous or {}).get("endpoints", [])
        }
        changes = {
            "added": [
                f"{method} {path}"
                for method, path in current_endpoint_map
                if (method, path) not in previous_endpoint_map
            ],
            "removed": [
                f"{method} {path}"
                for method, path in previous_endpoint_map
                if (method, path) not in current_endpoint_map
            ],
            "changed": [
                f"{method} {path}"
                for (method, path), item in current_endpoint_map.items()
                if (method, path) in previous_endpoint_map
                and item != previous_endpoint_map[(method, path)]
            ],
        }

        spec = {
            "id": ApiSpecStore._persist_next_id(),
            "workspace_id": workspace_id,
            "project_id": project_id,
            "service_name": service_name,
            "name": name,
            "source": source,
            "version": parsed.get("info", {}).get("version", "unknown"),
            "title": parsed.get("info", {}).get("title", "Untitled API"),
            "description": parsed.get("info", {}).get("description", ""),
            "endpoints": [e.model_dump() for e in endpoints],
            "endpoint_count": len(endpoints),
            "raw_spec": raw[:50000],
            "content_hash": hashlib.sha256(raw.encode()).hexdigest(),
            "revision": (previous or {}).get("revision", 0) + 1,
            "previous_spec_id": (previous or {}).get("id"),
            "changes": changes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = await ApiSpecStore._persist_add(spec)
        if previous and previous.get("content_hash") != spec["content_hash"]:
            await cls._mark_spec_dependents_stale(previous["id"], workspace_id)
        return saved

    @classmethod
    async def _mark_spec_dependents_stale(cls, spec_id: int, workspace_id: int) -> None:
        from .jira import TicketStore
        from .lifecycle import LifecycleService, TicketArtifactLinkStore
        from .notifications import NotificationService
        now = datetime.now(timezone.utc).isoformat()
        related_plan_ids = {
            plan["id"] for plan in TestPlanStore.list_by("spec_id", spec_id)
        }
        related_impact_ids = {
            impact["id"] for impact in ApiImpactStore.list_by("spec_id", spec_id)
        }
        ticket_ids = set()
        for link in TicketArtifactLinkStore.list_by("workspace_id", workspace_id):
            if (
                link.get("artifact_type") == "api_spec"
                and link.get("artifact_id") == spec_id
            ) or (
                link.get("artifact_type") == "test_plan"
                and link.get("artifact_id") in related_plan_ids
            ) or (
                link.get("artifact_type") == "api_impact"
                and link.get("artifact_id") in related_impact_ids
            ):
                ticket_ids.add(link.get("ticket_id"))
        for ticket_id in ticket_ids:
            ticket = TicketStore.get(ticket_id)
            if not ticket or not ticket.get("analysis_data"):
                continue
            await TicketStore.update_fields(
                ticket_id,
                {
                    "analysis_status": "stale",
                    "analysis_stale_at": now,
                    "updated_at": now,
                },
            )
            await LifecycleService.invalidate_review(
                ticket_id,
                workspace_id,
                "OpenAPI 规范已更新，需要重新核验 API 影响。",
            )
            await NotificationService.emit(
                workspace_id=workspace_id,
                event_type="analysis.stale",
                title=f"{ticket.get('key', ticket_id)} 分析已过期",
                message="关联 OpenAPI 规范已更新。",
                resource_type="ticket",
                resource_id=ticket_id,
                details={"source": "openapi", "spec_id": spec_id},
            )

    @classmethod
    def list_specs(cls, workspace_id: int) -> list[dict]:
        return [s for s in _api_specs.values() if s["workspace_id"] == workspace_id]

    @classmethod
    def get_spec(cls, spec_id: int, workspace_id: int) -> Optional[dict]:
        spec = _api_specs.get(spec_id)
        if spec and spec["workspace_id"] == workspace_id:
            return spec
        return None

    @classmethod
    async def analyze_ticket_impact(
        cls,
        spec_id: int,
        ticket: dict,
        sprint: dict,
        workspace_id: int,
    ) -> dict:
        """Compare Ticket API candidates with a concrete OpenAPI specification."""
        spec = cls.get_spec(spec_id, workspace_id)
        if not spec:
            raise ApiTestPlanError("API spec not found")
        if spec.get("project_id") is not None and spec.get("project_id") != sprint.get("project_id"):
            raise ApiTestPlanError("API spec belongs to another project")

        analysis = ticket.get("analysis_data") or {}
        candidates = analysis.get("api_candidates") or []
        endpoints = spec.get("endpoints") or []
        endpoint_index = {
            (item.get("method", "").upper(), item.get("path", "")): item
            for item in endpoints
        }
        impacts = []
        for candidate in candidates:
            match = re.search(
                r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+([^\s,;]+)",
                str(candidate),
                flags=re.IGNORECASE,
            )
            if not match:
                impacts.append({
                    "candidate": str(candidate),
                    "method": "",
                    "path": "",
                    "change_type": "unresolved",
                    "confirmation": "ai_inference",
                    "evidence": "候选接口格式无法与 OpenAPI Method/Path 对照",
                })
                continue
            method = match.group(1).upper()
            path = match.group(2).strip("`'\"()[]{}.,;:")
            endpoint = endpoint_index.get((method, path))
            impacts.append({
                "candidate": str(candidate),
                "method": method,
                "path": path,
                "change_type": "modify_or_reuse" if endpoint else "create",
                "confirmation": "spec_confirmed" if endpoint else "not_in_spec",
                "evidence": (
                    endpoint.get("summary")
                    or endpoint.get("description")
                    or "OpenAPI 中存在同 Method/Path"
                ) if endpoint else "当前 OpenAPI 中不存在该 Method/Path",
                "request_body": endpoint.get("request_body") if endpoint else None,
                "responses": endpoint.get("responses") if endpoint else {},
                "security": endpoint.get("security") if endpoint else [],
            })

        breaking_changes = []
        if any(item.get("confirmation") == "spec_confirmed" for item in impacts):
            for rule in analysis.get("validation_rules") or []:
                breaking_changes.append({
                    "type": "validation",
                    "level": "potential",
                    "description": rule,
                })
            for rule in analysis.get("permission_rules") or []:
                breaking_changes.append({
                    "type": "authorization",
                    "level": "potential",
                    "description": rule,
                })

        record = {
            "id": ApiImpactStore._persist_next_id(),
            "workspace_id": workspace_id,
            "project_id": sprint.get("project_id"),
            "sprint_id": sprint.get("id"),
            "ticket_id": ticket.get("id"),
            "spec_id": spec_id,
            "spec_version": spec.get("version"),
            "service_name": spec.get("service_name", ""),
            "impacts": impacts,
            "schema_changes": analysis.get("db_changes") or [],
            "validation_changes": analysis.get("validation_rules") or [],
            "breaking_changes": breaking_changes,
            "confirmed_count": sum(1 for item in impacts if item.get("confirmation") == "spec_confirmed"),
            "missing_count": sum(1 for item in impacts if item.get("confirmation") == "not_in_spec"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return await ApiImpactStore._persist_add(record)

    @classmethod
    def list_ticket_impacts(cls, ticket_id: int, workspace_id: int) -> list[dict]:
        return sorted(
            [
                item for item in ApiImpactStore.list_by("ticket_id", ticket_id)
                if item.get("workspace_id") == workspace_id
            ],
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )

    @classmethod
    async def delete_spec(cls, spec_id: int, workspace_id: int) -> bool:
        spec = cls.get_spec(spec_id, workspace_id)
        if spec:
            from .lifecycle import TicketArtifactLinkStore

            await ApiSpecStore._persist_delete(spec_id)
            related_plan_ids = set()
            for pid in list(_test_plans.keys()):
                if _test_plans[pid]["spec_id"] == spec_id:
                    related_plan_ids.add(pid)
                    await TestPlanStore._persist_delete(pid)
            related_impact_ids = {
                impact["id"]
                for impact in ApiImpactStore.list_by("spec_id", spec_id)
                if impact.get("workspace_id") == workspace_id
            }
            for impact_id in related_impact_ids:
                await ApiImpactStore._persist_delete(impact_id)
            for link in list(TicketArtifactLinkStore.list_by("workspace_id", workspace_id)):
                if (
                    link.get("artifact_type") == "api_spec"
                    and link.get("artifact_id") == spec_id
                ) or (
                    link.get("artifact_type") == "test_plan"
                    and link.get("artifact_id") in related_plan_ids
                ) or (
                    link.get("artifact_type") == "api_impact"
                    and link.get("artifact_id") in related_impact_ids
                ):
                    await TicketArtifactLinkStore._persist_delete(link["id"])
            return True
        return False

    # ── OpenAPI Parsing ──────────────────────────────────────────────────

    @staticmethod
    def _parse_openapi(raw: str) -> Optional[dict]:
        """Parse OpenAPI spec from JSON or YAML string."""
        # Try JSON first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try YAML (if pyyaml is available)
        try:
            import yaml
            return yaml.safe_load(raw)
        except ImportError:
            raise ApiTestPlanError(
                "Spec appears to be YAML but PyYAML is not installed. "
                "Install with: pip install pyyaml"
            )
        except Exception as e:
            raise ApiTestPlanError(f"Failed to parse spec: {e}")

    @staticmethod
    def _extract_endpoints(spec: dict) -> list[Endpoint]:
        """Extract all endpoints from an OpenAPI spec."""
        endpoints = []
        paths = spec.get("paths", {})
        if not paths:
            return endpoints

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "delete", "patch", "options", "head"):
                operation = path_item.get(method)
                if not operation:
                    continue
                endpoint = Endpoint(
                    path=path,
                    method=method.upper(),
                    summary=operation.get("summary", ""),
                    description=operation.get("description", ""),
                    parameters=operation.get("parameters", []),
                    request_body=operation.get("requestBody"),
                    responses=operation.get("responses", {}),
                    tags=operation.get("tags", []),
                    security=operation.get("security", []),
                )
                endpoints.append(endpoint)
        return endpoints

    # ── AI Test Plan Generation ──────────────────────────────────────────

    @classmethod
    async def generate_test_plan(
        cls,
        spec_id: int,
        workspace_id: int,
        provider=None,  # AIProvider instance, falls back to create_provider()
        focus_tags: Optional[list[str]] = None,
        ticket_ids: Optional[list[int]] = None,
    ) -> dict:
        """Generate an AI-powered test plan from a parsed OpenAPI spec."""
        spec = cls.get_spec(spec_id, workspace_id)
        if not spec:
            raise ApiTestPlanError("API spec not found")

        endpoints = spec.get("endpoints", [])
        if not endpoints:
            raise ApiTestPlanError("No endpoints found in spec")

        # Filter by tags if specified
        if focus_tags:
            endpoints = [e for e in endpoints if any(t in focus_tags for t in e.get("tags", []))]
            if not endpoints:
                raise ApiTestPlanError(f"No endpoints found with tags: {focus_tags}")

        # Try AI generation first
        scenarios = []
        ai_used = False

        try:
            if provider is None:
                from scopepilot.ai import create_provider
                provider = create_provider()

            if provider:
                scenarios = cls._ai_generate_scenarios(provider, spec, endpoints)
                ai_used = True
        except Exception as e:
            logger.warning(f"AI test generation failed, falling back to rule-based: {e}")

        # Fallback: rule-based generation
        if not scenarios:
            scenarios = cls._rule_based_scenarios(endpoints)

        # Coverage summary
        total_endpoints = len(endpoints)
        methods_covered = {}
        tags_covered = {}
        for ep in endpoints:
            m = ep.get("method", "GET")
            methods_covered[m] = methods_covered.get(m, 0) + 1
            for t in ep.get("tags", []):
                tags_covered[t] = tags_covered.get(t, 0) + 1

        plan_id = TestPlanStore._persist_next_id()
        plan = {
            "id": plan_id,
            "spec_id": spec_id,
            "workspace_id": workspace_id,
            "project_id": spec.get("project_id"),
            "ticket_ids": ticket_ids or [],
            "title": f"Test Plan: {spec.get('title', 'Untitled')}",
            "base_url": cls._infer_base_url(spec),
            "endpoints_analyzed": total_endpoints,
            "scenarios": scenarios,
            "scenario_count": len(scenarios),
            "coverage_summary": {
                "total_endpoints": total_endpoints,
                "total_scenarios": len(scenarios),
                "methods_covered": methods_covered,
                "tags_covered": tags_covered,
                "positive_scenarios": sum(1 for s in scenarios if s.get("test_type") == "positive"),
                "negative_scenarios": sum(1 for s in scenarios if s.get("test_type") == "negative"),
                "edge_scenarios": sum(1 for s in scenarios if s.get("test_type") in ("edge", "security")),
                "ai_generated": ai_used,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return await TestPlanStore._persist_add(plan)

    @classmethod
    def _ai_generate_scenarios(cls, provider, spec: dict, endpoints: list[dict]) -> list[dict]:
        """Use AI to generate intelligent test scenarios."""
        # Prepare endpoint summary for the prompt
        ep_summaries = []
        for i, ep in enumerate(endpoints[:30]):  # cap at 30 for prompt size
            ep_summaries.append(
                f"{i + 1}. {ep['method']} {ep['path']}"
                f"{' - ' + ep['summary'] if ep.get('summary') else ''}"
                f"{' [' + ', '.join(ep.get('tags', [])) + ']' if ep.get('tags') else ''}"
            )

        system_prompt = """You are an API testing expert. Generate comprehensive test scenarios for the given API endpoints.
For each endpoint, create test scenarios covering:
- Positive cases (happy path)
- Negative cases (error handling, invalid inputs)
- Edge cases (boundary values, empty inputs)
- Security cases (auth bypass, injection)

Return JSON array of scenarios, each with:
- endpoint: the URL path
- method: HTTP method
- scenario_name: short name
- description: what this tests
- test_input: example request body/params
- expected_status: HTTP status code
- expected_behavior: what should happen
- test_type: positive/negative/edge/security"""

        user_prompt = (
            f"API: {spec.get('title', 'Untitled')} v{spec.get('version', 'unknown')}\n\n"
            f"Endpoints:\n" + "\n".join(ep_summaries) +
            "\n\nGenerate test scenarios as a JSON array. Be thorough but practical."
        )

        result = provider.chat_json(system_prompt, user_prompt)
        scenarios = result if isinstance(result, list) else result.get("scenarios", [])

        # Validate and normalize
        valid = []
        for s in scenarios:
            if isinstance(s, dict) and s.get("endpoint") and s.get("method"):
                valid.append({
                    "endpoint": s["endpoint"],
                    "method": s["method"].upper(),
                    "scenario_name": s.get("scenario_name", f"Test {s['method']} {s['endpoint']}"),
                    "description": s.get("description", ""),
                    "test_input": s.get("test_input", {}),
                    "expected_status": s.get("expected_status", 200),
                    "expected_behavior": s.get("expected_behavior", ""),
                    "test_type": s.get("test_type", "positive"),
                })
        return valid

    @classmethod
    def _rule_based_scenarios(cls, endpoints: list[dict]) -> list[dict]:
        """Generate basic test scenarios from endpoint metadata (no AI)."""
        scenarios = []
        for ep in endpoints:
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            params = ep.get("parameters", [])

            # Positive: basic success case
            scenarios.append({
                "endpoint": path,
                "method": method,
                "scenario_name": f"[Positive] Basic {method} {path}",
                "description": f"Basic {method} request to verify endpoint responds correctly",
                "test_input": cls._sample_params(params),
                "expected_status": 200,
                "expected_behavior": "Returns successful response with expected data structure",
                "test_type": "positive",
            })

            # Negative: no auth
            if ep.get("security"):
                scenarios.append({
                    "endpoint": path,
                    "method": method,
                    "scenario_name": f"[Negative] No auth {method} {path}",
                    "description": "Request without authentication token",
                    "test_input": {},
                    "expected_status": 401,
                    "expected_behavior": "Returns 401 Unauthorized",
                    "test_type": "negative",
                })

            # Negative: invalid params
            if params:
                scenarios.append({
                    "endpoint": path,
                    "method": method,
                    "scenario_name": f"[Negative] Invalid params {method} {path}",
                    "description": "Request with invalid/missing required parameters",
                    "test_input": {},
                    "expected_status": 400,
                    "expected_behavior": "Returns 400 Bad Request with validation error",
                    "test_type": "negative",
                })

            # Edge: empty body for POST/PUT
            if method in ("POST", "PUT", "PATCH") and ep.get("request_body"):
                scenarios.append({
                    "endpoint": path,
                    "method": method,
                    "scenario_name": f"[Edge] Empty body {method} {path}",
                    "description": "Request with empty JSON body",
                    "test_input": {},
                    "expected_status": 400,
                    "expected_behavior": "Returns 400 Bad Request for missing required fields",
                    "test_type": "edge",
                })

        return scenarios

    @staticmethod
    def _sample_params(parameters: list[dict]) -> dict:
        """Generate sample parameter values from parameter definitions."""
        samples = {}
        for param in parameters:
            name = param.get("name", "")
            schema = param.get("schema", {})
            param_type = schema.get("type", "string")
            example = schema.get("example")
            if example:
                samples[name] = example
            elif param_type == "string":
                samples[name] = "test_string"
            elif param_type == "integer":
                samples[name] = 1
            elif param_type == "boolean":
                samples[name] = True
            elif param_type == "array":
                samples[name] = []
            else:
                samples[name] = None
        return samples

    @staticmethod
    def _infer_base_url(spec: dict) -> str:
        """Extract base URL from OpenAPI spec."""
        # Try servers array first
        servers = spec.get("servers", [])
        if servers and isinstance(servers, list):
            url = servers[0].get("url", "")
            return url

        # Try host + basePath (Swagger 2.0)
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        scheme = "https"
        if spec.get("schemes"):
            scheme = spec["schemes"][0]

        if host:
            return f"{scheme}://{host}{base_path}"

        return ""

    # ── Test Plan Retrieval ──────────────────────────────────────────────

    @classmethod
    def list_plans(cls, workspace_id: int) -> list[dict]:
        return [p for p in _test_plans.values() if p.get("workspace_id") == workspace_id]

    @classmethod
    def get_plan(cls, plan_id: int, workspace_id: int) -> Optional[dict]:
        plan = _test_plans.get(plan_id)
        if plan and plan.get("workspace_id") == workspace_id:
            return plan
        return None

    # ── Export ────────────────────────────────────────────────────────────

    @classmethod
    def export_markdown(cls, plan_id: int, workspace_id: int) -> str:
        """Export test plan as Markdown."""
        plan = cls.get_plan(plan_id, workspace_id)
        if not plan:
            raise ApiTestPlanError("Test plan not found")

        lines = [
            f"# {plan['title']}",
            f"",
            f"- **Endpoints analyzed:** {plan['endpoints_analyzed']}",
            f"- **Total scenarios:** {plan['scenario_count']}",
            f"- **Base URL:** {plan['base_url'] or '(not specified)'}",
            f"- **Generated:** {plan['created_at']}",
            f"",
            f"## Coverage Summary",
            f"",
        ]

        cov = plan.get("coverage_summary", {})
        lines.append(f"| Metric | Count |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Positive | {cov.get('positive_scenarios', 0)} |")
        lines.append(f"| Negative | {cov.get('negative_scenarios', 0)} |")
        lines.append(f"| Edge/Security | {cov.get('edge_scenarios', 0)} |")
        lines.append(f"| AI Generated | {'Yes' if cov.get('ai_generated') else 'No'} |")
        lines.append(f"")

        # Group by endpoint
        from collections import defaultdict
        by_endpoint: dict[str, list[dict]] = defaultdict(list)
        for s in plan.get("scenarios", []):
            key = f"{s['method']} {s['endpoint']}"
            by_endpoint[key].append(s)

        for ep_key in sorted(by_endpoint.keys()):
            scenarios = by_endpoint[ep_key]
            lines.append(f"### {ep_key}")
            lines.append(f"")
            for s in scenarios:
                test_type = s.get("test_type", "positive")
                tag = {"positive": "✅", "negative": "❌", "edge": "⚠️", "security": "🔒"}.get(test_type, "•")
                lines.append(f"{tag} **{s['scenario_name']}**")
                lines.append(f"  - {s['description']}")
                lines.append(f"  - Expected: `{s['expected_status']}` — {s['expected_behavior']}")
                if s.get("test_input"):
                    lines.append(f"  - Input: `{json.dumps(s['test_input'], ensure_ascii=False)}`")
                lines.append(f"")

        return "\n".join(lines)

    @classmethod
    def export_postman(cls, plan_id: int, workspace_id: int) -> dict:
        """Export test scenarios as Postman collection v2.1."""
        plan = cls.get_plan(plan_id, workspace_id)
        if not plan:
            raise ApiTestPlanError("Test plan not found")

        base_url = plan.get("base_url", "{{base_url}}")
        items = []
        seen_paths: set = set()

        for s in plan.get("scenarios", []):
            method = s.get("method", "GET").lower()
            path = s.get("endpoint", "/")
            url_parts = path.strip("/").split("/") if path.strip("/") else []

            # Build Postman request
            request = {
                "method": method.upper(),
                "header": [
                    {"key": "Content-Type", "value": "application/json"},
                    {"key": "Authorization", "value": "Bearer {{token}}"},
                ],
                "url": {
                    "raw": f"{base_url}{path}",
                    "protocol": base_url.split("://")[0] if "://" in base_url else "https",
                    "host": base_url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0] if base_url else "localhost",
                    "path": url_parts,
                },
                "description": f"{s.get('scenario_name', '')} — {s.get('description', '')}",
            }

            # Add request body for POST/PUT/PATCH
            if method.upper() in ("POST", "PUT", "PATCH") and s.get("test_input"):
                request["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(s["test_input"], indent=2),
                }

            # Expected status as test
            events = [
                {
                    "listen": "test",
                    "script": {
                        "exec": [
                            f'pm.test("Status code is {s["expected_status"]}", function () {{',
                            f'    pm.response.to.have.status({s["expected_status"]});',
                            "});",
                        ],
                        "type": "text/javascript",
                    },
                }
            ]

            name = f"{method.upper()} {path} - {s.get('scenario_name', '')[:40]}"
            items.append({
                "name": name,
                "event": events,
                "request": request,
            })
            seen_paths.add(name)

        collection = {
            "info": {
                "name": plan["title"],
                "description": f"Auto-generated test plan from OpenAPI spec\nScenarios: {plan['scenario_count']}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": items,
        }
        return collection
