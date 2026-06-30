"""Tests for FigmaService: URL parsing, design extraction, implications."""
import asyncio
import pytest
from app.services.figma import FigmaService, FigmaError
from app.services.figma import FigmaAnalysisStore, _figma_analyses


class TestFigmaUrlParsing:
    """Figma URL parsing."""

    def test_file_url(self):
        result = FigmaService.parse_figma_url(
            "https://www.figma.com/file/abc123def456/MyDesign"
        )
        assert result is not None
        assert result["file_key"] == "abc123def456"
        assert result["file_name"] == "MyDesign"
        assert result["node_id"] is None

    def test_design_url(self):
        result = FigmaService.parse_figma_url(
            "https://www.figma.com/design/xyz789ghi012/AppDesign"
        )
        assert result is not None
        assert result["file_key"] == "xyz789ghi012"
        assert result["file_name"] == "AppDesign"

    def test_url_with_node_id(self):
        result = FigmaService.parse_figma_url(
            "https://www.figma.com/file/abc123def456/MyDesign?node-id=123:456"
        )
        assert result is not None
        assert result["file_key"] == "abc123def456"
        assert result["node_id"] == "123:456"

    def test_invalid_url(self):
        result = FigmaService.parse_figma_url("https://google.com")
        assert result is None

    def test_empty_url(self):
        result = FigmaService.parse_figma_url("")
        assert result is None


class TestFrameExtraction:
    """Extract frames from Figma document trees."""

    def test_empty_document(self):
        frames = FigmaService.extract_frames({"type": "DOCUMENT", "children": []})
        assert frames == []

    def test_single_frame(self):
        doc = {
            "type": "DOCUMENT",
            "children": [
                {
                    "type": "CANVAS",
                    "children": [
                        {"type": "FRAME", "name": "HomePage", "id": "1:1", "visible": True, "children": []},
                    ],
                },
            ],
        }
        frames = FigmaService.extract_frames(doc)
        assert len(frames) == 1
        assert frames[0]["name"] == "HomePage"
        assert frames[0]["type"] == "FRAME"

    def test_nested_components(self):
        doc = {
            "type": "DOCUMENT",
            "children": [
                {
                    "type": "CANVAS",
                    "children": [
                        {"type": "FRAME", "name": "Page", "id": "1:1", "visible": True, "children": [
                            {"type": "COMPONENT", "name": "Button", "id": "2:1", "visible": True, "children": []},
                            {"type": "INSTANCE", "name": "PrimaryBtn", "id": "3:1", "visible": True, "children": []},
                        ]},
                    ],
                },
            ],
        }
        frames = FigmaService.extract_frames(doc)
        assert len(frames) == 3  # 1 frame + 1 component + 1 instance


class TestTextExtraction:
    """Extract text nodes from Figma documents."""

    def test_extract_texts(self):
        doc = {
            "type": "DOCUMENT",
            "children": [
                {
                    "type": "CANVAS",
                    "children": [
                        {
                            "type": "TEXT",
                            "id": "1:1",
                            "name": "Title",
                            "characters": "Welcome",
                            "style": {"fontFamily": "Inter", "fontSize": 24},
                        },
                        {
                            "type": "FRAME",
                            "name": "Form",
                            "children": [
                                {"type": "TEXT", "id": "2:1", "name": "Label",
                                 "characters": "Email", "style": {"fontFamily": "Inter", "fontSize": 14}},
                            ],
                        },
                    ],
                },
            ],
        }
        texts = FigmaService.extract_text_nodes(doc)
        assert len(texts) == 2
        assert texts[0]["characters"] == "Welcome"
        assert texts[1]["characters"] == "Email"


class TestDesignTokenExtraction:
    """Extract design tokens from Figma documents."""

    def test_token_extraction(self):
        doc = {
            "type": "DOCUMENT",
            "children": [
                {
                    "type": "FRAME",
                    "name": "Card",
                    "paddingTop": 16, "paddingRight": 24, "paddingBottom": 16, "paddingLeft": 24,
                    "cornerRadius": 8,
                    "fills": [{"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0}, "opacity": 1}],
                    "children": [
                        {
                            "type": "TEXT",
                            "name": "Title",
                            "characters": "Hello",
                            "style": {"fontFamily": "Inter", "fontSize": 18, "fontWeight": 600},
                        },
                    ],
                },
            ],
        }
        tokens = FigmaService.extract_design_tokens(doc)
        assert "Card" in tokens["colors"]
        assert 16 in tokens["spacing"]
        assert 24 in tokens["spacing"]
        assert 8 in tokens["border_radius"]
        assert "Inter-18" in tokens["typography"]


class TestRuleBasedImplications:
    """Generate backend implications from design analysis."""

    def test_screen_detection(self):
        frames = [{"type": "FRAME", "name": "Login Screen", "id": "1:1", "visible": True, "children_count": 5}]
        texts = []
        tokens = {"colors": {}, "spacing": [], "typography": {}}

        implications = FigmaService._rule_based_implications(frames, texts, tokens, "")
        types = [i["type"] for i in implications]
        assert "page" in types

    def test_auth_detection(self):
        frames = [{"type": "FRAME", "name": "Login Page", "id": "1:1", "visible": True, "children_count": 3}]
        texts = [{"characters": "Sign In", "style": {}, "id": "1:2", "name": "Title",
                  "absolute_bounding_box": {}}]
        tokens = {"colors": {}, "spacing": [], "typography": {}}

        implications = FigmaService._rule_based_implications(frames, texts, tokens, "")
        types = [i["type"] for i in implications]
        assert "auth" in types

    def test_form_detection(self):
        frames = [{"type": "FRAME", "name": "Contact Form", "id": "1:1", "visible": True, "children_count": 8}]
        texts = [{"characters": "Submit", "style": {}, "id": "1:2", "name": "Button",
                  "absolute_bounding_box": {}}]
        tokens = {"colors": {}, "spacing": [], "typography": {}}

        implications = FigmaService._rule_based_implications(frames, texts, tokens, "")
        types = [i["type"] for i in implications]
        assert "backend" in types  # form detection creates type "backend"


class TestAnalysisCRUD:
    """Save, list, get, delete Figma analyses."""

    WS_ID = 1

    def test_save_and_list(self):
        analysis = asyncio.run(FigmaService.save_analysis({
            "figma_url": "https://figma.com/file/abc/test",
            "file_key": "abc",
            "file_name": "Test",
            "frame_count": 3,
            "text_node_count": 5,
            "implications": [{"type": "page", "priority": "high", "title": "Test", "description": "D", "detail": {}}],
            "ai_used": False,
            "design_tokens": {"colors": {}, "spacing": [], "typography": {}},
            "frames": [],
        }, self.WS_ID))

        assert analysis["id"] == 1
        assert analysis["frame_count"] == 3

        analyses = FigmaService.list_analyses(self.WS_ID)
        assert len(analyses) == 1

    def test_get_and_delete(self):
        a = asyncio.run(FigmaService.save_analysis({"figma_url": "https://figma.com/file/x/test",
                                         "file_key": "x", "file_name": "X",
                                         "frame_count": 0, "text_node_count": 0,
                                         "implications": [], "ai_used": False,
                                         "design_tokens": {}, "frames": []}, self.WS_ID))

        found = FigmaService.get_analysis(a["id"], self.WS_ID)
        assert found is not None

        assert asyncio.run(FigmaService.delete_analysis(a["id"], self.WS_ID)) is True
        assert FigmaService.get_analysis(a["id"], self.WS_ID) is None

    def test_workspace_isolation(self):
        a = asyncio.run(FigmaService.save_analysis({"figma_url": "https://figma.com/file/x/test",
                                         "file_key": "x", "file_name": "X",
                                         "frame_count": 0, "text_node_count": 0,
                                         "implications": [], "ai_used": False,
                                         "design_tokens": {}, "frames": []}, self.WS_ID))
        assert FigmaService.get_analysis(a["id"], 99) is None
