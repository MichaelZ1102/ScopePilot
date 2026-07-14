"""Figma integration service - read design files, extract fields, generate backend implications.

Phase 4: In-memory store persisted to local JSON via SqliteStore.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from ..database import SqliteStore

logger = logging.getLogger(__name__)


class FigmaAnalysisStore(SqliteStore):
    _entity_name = "figma_analyses"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_figma_analyses = FigmaAnalysisStore._store


class FigmaError(Exception):
    """Base exception for Figma service."""


class FigmaService:
    """Service for interacting with Figma REST API and analyzing designs."""

    # ── Figma File Reading ───────────────────────────────────────────────

    @classmethod
    def parse_figma_url(cls, url: str) -> Optional[dict]:
        """Parse a Figma URL to extract file key and optional node/frame IDs.

        Supports formats:
        - https://www.figma.com/file/xxx/Name
        - https://www.figma.com/design/xxx/Name
        - https://www.figma.com/file/xxx/Name?node-id=123:456
        - https://www.figma.com/design/xxx/Name?node-id=123:456
        """
        parsed_url = urlparse(url)
        match = re.search(
            r'/(?:file|design)/([a-zA-Z0-9]{10,60})(?:/([^/?]+))?',
            parsed_url.path,
        )
        if match:
            node_id = parse_qs(parsed_url.query).get("node-id", [None])[0]
            return {
                "file_key": match.group(1),
                "file_name": unquote(match.group(2) or ""),
                "node_id": unquote(node_id) if node_id else None,
            }
        return None

    @staticmethod
    def normalize_node_ids(value: str) -> list[str]:
        """Normalize Figma node IDs from form input or URL query parameters."""
        result: list[str] = []
        for raw in re.split(r"[,\s]+", unquote(value or "").strip()):
            if not raw:
                continue
            node_id = raw.replace("-", ":")
            if not re.fullmatch(r"\d+:\d+", node_id):
                raise FigmaError(f"Invalid Figma node ID: {raw}")
            if node_id not in result:
                result.append(node_id)
        return result

    @classmethod
    async def fetch_file_info(
        cls, file_key: str, access_token: str,
    ) -> dict:
        """Fetch Figma file metadata via the REST API."""
        headers = {
            "X-Figma-Token": access_token,
            "Content-Type": "application/json",
        }

        file_url = f"https://api.figma.com/v1/files/{file_key}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(file_url, headers=headers, timeout=30)

        if resp.status_code == 403:
            raise FigmaError("Figma API access denied. Check your personal access token.")
        if resp.status_code == 404:
            raise FigmaError("Figma file not found. Check the URL.")
        if resp.status_code != 200:
            raise FigmaError(f"Figma API error: {resp.status_code}")

        data = resp.json()
        return {
            "name": data.get("name", ""),
            "last_modified": data.get("lastModified", ""),
            "version": data.get("version", ""),
            "document": data.get("document", {}),
            "components": data.get("components", {}),
            "styles": data.get("styles", {}),
        }

    @classmethod
    async def fetch_node_images(
        cls, file_key: str, node_ids: list[str], access_token: str,
    ) -> dict:
        """Fetch rendered images of specific Figma nodes."""
        headers = {"X-Figma-Token": access_token}
        node_ids_str = ",".join(node_ids)
        url = f"https://api.figma.com/v1/images/{file_key}?ids={node_ids_str}&format=png&scale=2"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30)

        if resp.status_code != 200:
            raise FigmaError(f"Failed to fetch node images: {resp.status_code}")
        return resp.json().get("images", {})

    @classmethod
    async def fetch_nodes(
        cls, file_key: str, node_ids: list[str], access_token: str,
    ) -> dict[str, dict]:
        """Fetch the requested Figma node documents instead of analyzing the full file."""
        headers = {"X-Figma-Token": access_token}
        url = f"https://api.figma.com/v1/files/{file_key}/nodes"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=headers,
                params={"ids": ",".join(node_ids)},
                timeout=30,
            )
        if resp.status_code == 403:
            raise FigmaError("Figma API access denied while reading the selected node.")
        if resp.status_code != 200:
            raise FigmaError(f"Failed to fetch selected Figma node: {resp.status_code}")
        nodes = resp.json().get("nodes", {})
        return {
            node_id: item
            for node_id, item in nodes.items()
            if isinstance(item, dict) and isinstance(item.get("document"), dict)
        }

    # ── Design Analysis ──────────────────────────────────────────────────

    @classmethod
    def extract_frames(cls, document: dict) -> list[dict]:
        """Extract all frames/pages from a Figma document tree."""
        frames = []

        def walk(node: dict, depth: int = 0, page_id: str = "", page_name: str = ""):
            if depth > 20:
                return
            node_type = node.get("type", "")
            name = node.get("name", "")
            children = node.get("children", [])
            if node_type == "CANVAS":
                page_id = node.get("id", "")
                page_name = name

            if node_type in ("FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE", "GROUP"):
                frame_info = {
                    "id": node.get("id", ""),
                    "name": name,
                    "type": node_type,
                    "page_id": page_id,
                    "page_name": page_name,
                    "visible": node.get("visible", True),
                    "children_count": len(children),
                    "absolute_bounding_box": node.get("absoluteBoundingBox", {}),
                    "corner_radius": node.get("cornerRadius"),
                    "item_spacing": node.get("itemSpacing"),
                    "padding": {
                        "top": node.get("paddingTop"),
                        "right": node.get("paddingRight"),
                        "bottom": node.get("paddingBottom"),
                        "left": node.get("paddingLeft"),
                    },
                    "layout_mode": node.get("layoutMode"),
                    "primary_axis_sizing_mode": node.get("primaryAxisSizingMode"),
                    "counter_axis_sizing_mode": node.get("counterAxisSizingMode"),
                    "background_color": node.get("backgroundColor"),
                }
                frames.append(frame_info)

            for child in children:
                walk(child, depth + 1, page_id, page_name)

        walk(document)
        return frames

    @classmethod
    def extract_pages(cls, document: dict) -> list[dict]:
        """Return file page metadata without inventing unavailable design content."""
        pages = []
        for page in document.get("children", []):
            if page.get("type") != "CANVAS":
                continue
            children = page.get("children", [])
            pages.append({
                "id": page.get("id", ""),
                "name": page.get("name", ""),
                "frame_count": sum(
                    1 for child in children
                    if child.get("type") in {"FRAME", "COMPONENT", "COMPONENT_SET"}
                ),
                "children_count": len(children),
            })
        return pages

    @classmethod
    def extract_text_nodes(cls, document: dict) -> list[dict]:
        """Extract all text nodes and their content from a Figma document."""
        texts = []

        def walk(node: dict, depth: int = 0):
            if depth > 20:
                return
            if node.get("type") == "TEXT":
                style = node.get("style", {})
                texts.append({
                    "id": node.get("id", ""),
                    "name": node.get("name", ""),
                    "characters": node.get("characters", ""),
                    "style": {
                        "font_family": style.get("fontFamily"),
                        "font_size": style.get("fontSize"),
                        "font_weight": style.get("fontWeight"),
                        "line_height": style.get("lineHeightPx"),
                        "letter_spacing": style.get("letterSpacing"),
                        "text_align": style.get("textAlignHorizontal"),
                    },
                    "absolute_bounding_box": node.get("absoluteBoundingBox", {}),
                })
            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(document)
        return texts

    @classmethod
    def extract_design_tokens(cls, document: dict) -> dict:
        """Extract design tokens (colors, spacing, typography) from a Figma doc."""
        tokens = {
            "colors": {},
            "spacing": set(),
            "typography": {},
            "border_radius": set(),
        }

        def walk(node: dict, depth: int = 0):
            if depth > 20:
                return

            # Collect fills (colors)
            fills = node.get("fills", [])
            for fill in fills:
                if fill.get("type") == "SOLID":
                    color = fill.get("color", {})
                    opacity = fill.get("opacity", 1)
                    if color:
                        rgba = (
                            f"rgba({int(color.get('r', 0) * 255)}, "
                            f"{int(color.get('g', 0) * 255)}, "
                            f"{int(color.get('b', 0) * 255)}, "
                            f"{opacity})"
                        )
                        name = node.get("name", "unnamed")
                        tokens["colors"][name] = rgba

            # Collect spacing
            for attr in ("itemSpacing", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft"):
                val = node.get(attr)
                if val is not None:
                    tokens["spacing"].add(val)

            # Collect border radius
            cr = node.get("cornerRadius")
            if cr is not None:
                tokens["border_radius"].add(cr)

            # Collect typography from text nodes
            if node.get("type") == "TEXT":
                style = node.get("style", {})
                font_family = style.get("fontFamily")
                font_size = style.get("fontSize")
                if font_family and font_size:
                    key = f"{font_family}-{font_size}"
                    if key not in tokens["typography"]:
                        tokens["typography"][key] = {
                            "font_family": font_family,
                            "font_size": font_size,
                            "font_weight": style.get("fontWeight"),
                            "line_height": style.get("lineHeightPx"),
                        }

            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(document)
        tokens["spacing"] = sorted(tokens["spacing"])
        tokens["border_radius"] = sorted(tokens["border_radius"])
        return tokens

    # ── Backend Implications ─────────────────────────────────────────────

    @classmethod
    def generate_implications(
        cls,
        frames: list[dict],
        texts: list[dict],
        tokens: dict,
        ticket_summary: str = "",
        ai_provider=None,
    ) -> dict:
        """Generate backend implications from Figma design analysis.

        Uses AI if available, otherwise rule-based heuristics.
        """
        # Rule-based implications
        implications = cls._rule_based_implications(frames, texts, tokens, ticket_summary)

        # Try AI enhancement if provider is given
        ai_used = False
        if ai_provider:
            try:
                ai_implications = cls._ai_implications(
                    ai_provider, frames, texts, tokens, ticket_summary,
                )
                if ai_implications:
                    implications = ai_implications
                    ai_used = True
            except Exception as e:
                logger.warning(f"AI implications failed, using rule-based: {e}")

        return {
            "implications": implications,
            "frame_count": len(frames),
            "text_node_count": len(texts),
            "token_count": {
                "colors": len(tokens.get("colors", {})),
                "spacing": len(tokens.get("spacing", [])),
                "typography": len(tokens.get("typography", {})),
            },
            "ai_used": ai_used,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _rule_based_implications(
        frames: list[dict],
        texts: list[dict],
        tokens: dict,
        ticket_summary: str,
    ) -> list[dict]:
        """Generate rule-based backend implications from design data."""
        implications = []

        # Screen/page detection
        screens = [f for f in frames if f["type"] in ("FRAME", "COMPONENT_SET")]
        if screens:
            implications.append({
                "type": "page",
                "priority": "high",
                "title": f"需创建 {len(screens)} 个新页面/视图",
                "description": f"设计中包含 {len(screens)} 个框架/页面: "
                               f"{', '.join(s['name'] for s in screens[:5])}",
                "detail": {
                    "page_names": [s["name"] for s in screens],
                    "framework": "React + TypeScript 页面组件",
                },
            })

        # Data display (tables, lists)
        data_displays = [f for f in frames if "table" in f["name"].lower()
                         or "list" in f["name"].lower() or "grid" in f["name"].lower()]
        if data_displays:
            implications.append({
                "type": "api",
                "priority": "high",
                "title": f"需实现 {len(data_displays)} 个列表/表格 API 端点",
                "description": f"设计包含列表/表格视图，需要分页、排序、过滤 API 支持",
                "detail": {
                    "components": [d["name"] for d in data_displays],
                    "suggested_endpoints": [
                        "GET /api/items?page=&page_size=&sort=&filter=",
                        "GET /api/items/:id",
                    ],
                },
            })

        # Form detection
        forms = [f for f in frames if "form" in f["name"].lower()
                 or "input" in f["name"].lower() or "field" in f["name"].lower()]
        if forms:
            form_implications = {
                "type": "backend",
                "priority": "high",
                "title": f"需创建 {len(forms)} 个表单的提交/验证逻辑",
                "description": f"设计包含表单组件，需要后端验证和数据持久化",
                "detail": {
                    "form_components": [f["name"] for f in forms],
                    "suggested": "Pydantic schemas + POST/PUT endpoints + DB models",
                },
            }
            implications.append(form_implications)

        # Text fields to data model
        text_fields = [t for t in texts if t["characters"].strip()]
        if text_fields:
            # Extract field-like texts (non-heading, non-label patterns)
            data_fields = [t for t in text_fields if len(t["characters"]) < 100
                          and "{" not in t["characters"]]
            if data_fields:
                implications.append({
                    "type": "model",
                    "priority": "medium",
                    "title": f"设计包含 {len(data_fields)} 个文本/标签字段",
                    "description": f"需要分析这些字段以定义数据模型和 API 响应结构",
                    "detail": {
                        "text_fields": [t["characters"][:50] for t in data_fields[:10]],
                        "total_text_nodes": len(text_fields),
                    },
                })

        # Authentication screens
        auth_screens = [f for f in frames if any(
            kw in f["name"].lower() for kw in ["login", "signin", "sign up", "register", "forgot", "auth"]
        )]
        if auth_screens:
            implications.append({
                "type": "auth",
                "priority": "high",
                "title": "需要认证功能",
                "description": f"设计包含登录/注册界面，需要实现身份验证流程",
                "detail": {
                    "screens": [s["name"] for s in auth_screens],
                    "suggested": "JWT token auth + user registration + password reset",
                },
            })

        # Design tokens that affect backend
        colors = tokens.get("colors", {})
        spacing = tokens.get("spacing", [])
        typography = tokens.get("typography", {})

        if colors or spacing or typography:
            implications.append({
                "type": "design_tokens",
                "priority": "low",
                "title": "设计系统 Token 提取",
                "description": f"从设计中提取 {len(colors)} 种颜色、{len(spacing)} 个间距值、"
                               f"{len(typography)} 种字体样式 - 需同步到前端主题配置",
                "detail": {
                    "color_count": len(colors),
                    "spacing_values": list(spacing),
                    "font_styles": list(typography.keys()),
                },
            })

        return implications

    @staticmethod
    def _ai_implications(provider, frames, texts, tokens, ticket_summary) -> list[dict]:
        """Use AI to generate more nuanced backend implications."""
        frame_summary = "\n".join(
            f"  - {f['type']}: {f['name']} ({f.get('children_count', 0)} children)"
            for f in frames[:20]
        )
        text_summary = "\n".join(
            f"  - \"{t['characters'][:60]}\" [{t['style'].get('font_family', '?')}]"
            for t in texts[:15]
        )

        system_prompt = """You are a senior backend engineer analyzing Figma designs.
For each design, generate a concise list of backend implications.

Return a JSON array of implications, each with:
- type: "page" | "api" | "model" | "auth" | "design_tokens" | "migration"
- priority: "high" | "medium" | "low"
- title: short title in Chinese
- description: what backend work is needed
- detail: dict with specific suggestions"""

        user_prompt = (
            f"Ticket: {ticket_summary or '(no ticket context)'}\n\n"
            f"Figma Design Analysis:\n"
            f"Frames ({len(frames)}):\n{frame_summary}\n"
            f"Text nodes ({len(texts)}):\n{text_summary}\n"
            f"Colors: {len(tokens.get('colors', {}))}, "
            f"Spacing: {len(tokens.get('spacing', []))}, "
            f"Typography: {len(tokens.get('typography', {}))}\n\n"
            f"Generate backend implications as JSON array."
        )

        result = provider.chat_json(system_prompt, user_prompt)
        if isinstance(result, list):
            return result
        return result.get("implications", [])

    # ── CRUD for analyses ────────────────────────────────────────────────

    @classmethod
    async def save_analysis(cls, analysis: dict, workspace_id: int) -> dict:
        analysis["id"] = FigmaAnalysisStore._persist_next_id()
        analysis["workspace_id"] = workspace_id
        analysis["created_at"] = datetime.now(timezone.utc).isoformat()
        return await FigmaAnalysisStore._persist_add(analysis)

    @classmethod
    def get_analysis(cls, analysis_id: int, workspace_id: int) -> Optional[dict]:
        a = _figma_analyses.get(analysis_id)
        if a and a.get("workspace_id") == workspace_id:
            return a
        return None

    @classmethod
    def list_analyses(cls, workspace_id: int, project_id: Optional[int] = None) -> list[dict]:
        analyses = [a for a in _figma_analyses.values() if a.get("workspace_id") == workspace_id]
        if project_id is not None:
            analyses = [a for a in analyses if a.get("project_id") == project_id]
        return sorted(analyses, key=lambda item: item.get("created_at", ""), reverse=True)

    @classmethod
    async def delete_analysis(cls, analysis_id: int, workspace_id: int) -> bool:
        a = cls.get_analysis(analysis_id, workspace_id)
        if a:
            await FigmaAnalysisStore._persist_delete(analysis_id)
            return True
        return False
