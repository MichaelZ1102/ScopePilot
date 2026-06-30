"""Tests for ApiTestPlannerService: OpenAPI parsing, spec storage, test generation."""
import asyncio
import pytest
from app.services.api_test_planner import (
    ApiTestPlannerService, ApiTestPlanError,
    ApiSpecStore, TestPlanStore,
    Endpoint,
)
from app.services.api_test_planner import _api_specs, _test_plans


# A minimal OpenAPI 3.0 spec for testing
SAMPLE_OPENAPI = """
{
    "openapi": "3.0.0",
    "info": {
        "title": "Pet Store API",
        "version": "1.0.0",
        "description": "A sample pet store API"
    },
    "paths": {
        "/pets": {
            "get": {
                "summary": "List all pets",
                "tags": ["pets"],
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "A list of pets"}
                }
            },
            "post": {
                "summary": "Create a pet",
                "tags": ["pets"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"}
                        }
                    }
                },
                "security": [{"api_key": []}],
                "responses": {
                    "201": {"description": "Created"}
                }
            }
        },
        "/pets/{pet_id}": {
            "get": {
                "summary": "Get a pet by ID",
                "tags": ["pets"],
                "parameters": [
                    {"name": "pet_id", "in": "path", "required": true, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "A pet"}
                }
            },
            "delete": {
                "summary": "Delete a pet",
                "tags": ["pets"],
                "security": [{"api_key": []}],
                "responses": {
                    "204": {"description": "Deleted"}
                }
            }
        },
        "/health": {
            "get": {
                "summary": "Health check",
                "tags": ["system"],
                "responses": {
                    "200": {"description": "OK"}
                }
            }
        }
    }
}
"""


class TestOpenAPIParsing:
    """OpenAPI spec parsing and endpoint extraction."""

    WS_ID = 1

    def test_parse_json_spec(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(
            SAMPLE_OPENAPI, "Pet Store", "inline", self.WS_ID,
        ))

        assert spec["title"] == "Pet Store API"
        assert spec["version"] == "1.0.0"
        assert spec["endpoint_count"] == 5  # GET /pets, POST /pets, GET /pets/{pet_id}, DELETE /pets/{pet_id}, GET /health
        assert spec["id"] == 1

    def test_list_specs(self):
        asyncio.run(ApiTestPlannerService.create_spec_from_content(SAMPLE_OPENAPI, "A", "inline", self.WS_ID))
        asyncio.run(ApiTestPlannerService.create_spec_from_content(SAMPLE_OPENAPI, "B", "inline", self.WS_ID))

        specs = ApiTestPlannerService.list_specs(self.WS_ID)
        assert len(specs) == 2

    def test_get_spec(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(SAMPLE_OPENAPI, "X", "inline", self.WS_ID))
        assert ApiTestPlannerService.get_spec(spec["id"], self.WS_ID) is not None
        assert ApiTestPlannerService.get_spec(spec["id"], 99) is None

    def test_delete_spec(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(SAMPLE_OPENAPI, "X", "inline", self.WS_ID))
        assert asyncio.run(ApiTestPlannerService.delete_spec(spec["id"], self.WS_ID)) is True
        assert ApiTestPlannerService.get_spec(spec["id"], self.WS_ID) is None

    def test_invalid_json_raises(self):
        with pytest.raises(ApiTestPlanError, match="could not parse"):
            asyncio.run(ApiTestPlannerService.create_spec_from_content(
                "not valid json", "Bad", "inline", self.WS_ID,
            ))


class TestEndpointExtraction:
    """Low-level endpoint extraction."""

    def test_extract_endpoints_count(self):
        parsed = ApiTestPlannerService._parse_openapi(SAMPLE_OPENAPI)
        endpoints = ApiTestPlannerService._extract_endpoints(parsed)
        assert len(endpoints) == 5

    def test_extract_methods(self):
        parsed = ApiTestPlannerService._parse_openapi(SAMPLE_OPENAPI)
        endpoints = ApiTestPlannerService._extract_endpoints(parsed)
        methods = [e.method for e in endpoints]
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods

    def test_extract_with_security(self):
        parsed = ApiTestPlannerService._parse_openapi(SAMPLE_OPENAPI)
        endpoints = ApiTestPlannerService._extract_endpoints(parsed)
        secured = [e for e in endpoints if e.security]
        assert len(secured) == 2  # POST /pets and DELETE /pets/{pet_id}


class BaseURLInference:
    """Base URL extraction from spec."""

    def test_servers_array(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "servers": [{"url": "https://api.example.com/v1"}],
            "paths": {},
        }
        url = ApiTestPlannerService._infer_base_url(spec)
        assert url == "https://api.example.com/v1"

    def test_host_base_path(self):
        spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "schemes": ["https"],
            "paths": {},
        }
        url = ApiTestPlannerService._infer_base_url(spec)
        assert url == "https://api.example.com/v1"

    def test_no_server_info(self):
        spec = {"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}, "paths": {}}
        url = ApiTestPlannerService._infer_base_url(spec)
        assert url == ""


class TestRuleBasedScenarios:
    """Test the fallback rule-based scenario generation."""

    def test_basic_get(self):
        endpoints = [
            Endpoint(path="/users", method="GET", summary="List users").model_dump(),
        ]
        scenarios = ApiTestPlannerService._rule_based_scenarios(endpoints)
        assert len(scenarios) >= 1
        assert scenarios[0]["method"] == "GET"
        assert scenarios[0]["endpoint"] == "/users"
        assert scenarios[0]["test_type"] == "positive"

    def test_secured_endpoint(self):
        endpoints = [
            Endpoint(path="/admin", method="GET", security=[{"api_key": []}], tags=["admin"]).model_dump(),
        ]
        scenarios = ApiTestPlannerService._rule_based_scenarios(endpoints)
        types = [s["test_type"] for s in scenarios]
        assert "negative" in types  # no-auth test

    def test_post_with_body(self):
        endpoints = [
            Endpoint(path="/items", method="POST",
                     request_body={"content": {"application/json": {"schema": {"type": "object"}}}},
                     tags=["items"]).model_dump(),
        ]
        scenarios = ApiTestPlannerService._rule_based_scenarios(endpoints)
        types = [s["test_type"] for s in scenarios]
        assert "edge" in types  # empty body test


class TestTestPlanGeneration:
    """Full test plan generation from spec."""

    WS_ID = 1

    def test_full_flow(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(
            SAMPLE_OPENAPI, "Pet Store", "inline", self.WS_ID,
        ))
        plan = asyncio.run(ApiTestPlannerService.generate_test_plan(
            spec_id=spec["id"],
            workspace_id=self.WS_ID,
        ))

        assert plan["spec_id"] == spec["id"]
        assert plan["endpoints_analyzed"] == 5
        assert plan["scenario_count"] >= 5  # at least 1 per endpoint
        assert plan["coverage_summary"]["total_endpoints"] == 5
        assert plan["coverage_summary"]["total_scenarios"] == plan["scenario_count"]

    def test_plan_list_and_get(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(
            SAMPLE_OPENAPI, "Pet Store", "inline", self.WS_ID,
        ))
        plan = asyncio.run(ApiTestPlannerService.generate_test_plan(spec_id=spec["id"], workspace_id=self.WS_ID))

        plans = ApiTestPlannerService.list_plans(self.WS_ID)
        assert len(plans) == 1

        fetched = ApiTestPlannerService.get_plan(plan["id"], self.WS_ID)
        assert fetched is not None
        assert fetched["id"] == plan["id"]

    def test_plan_scoping(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(
            SAMPLE_OPENAPI, "Pet Store", "inline", self.WS_ID,
        ))
        plan = asyncio.run(ApiTestPlannerService.generate_test_plan(spec_id=spec["id"], workspace_id=self.WS_ID))

        # Wrong workspace should not find it
        assert ApiTestPlannerService.get_plan(plan["id"], 99) is None

    def test_markdown_export(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(
            SAMPLE_OPENAPI, "Pet Store", "inline", self.WS_ID,
        ))
        plan = asyncio.run(ApiTestPlannerService.generate_test_plan(spec_id=spec["id"], workspace_id=self.WS_ID))

        md = ApiTestPlannerService.export_markdown(plan["id"], self.WS_ID)
        assert "# Test Plan: Pet Store API" in md
        assert "## Coverage Summary" in md
        assert "GET /pets" in md
        assert "POST /pets" in md

    def test_postman_export(self):
        spec = asyncio.run(ApiTestPlannerService.create_spec_from_content(
            SAMPLE_OPENAPI, "Pet Store", "inline", self.WS_ID,
        ))
        plan = asyncio.run(ApiTestPlannerService.generate_test_plan(spec_id=spec["id"], workspace_id=self.WS_ID))

        collection = ApiTestPlannerService.export_postman(plan["id"], self.WS_ID)
        assert collection["info"]["name"] == plan["title"]
        assert len(collection["item"]) > 0
        # At least one item should have a test script
        assert collection["item"][0].get("event", [])
