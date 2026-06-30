"""Local codebase scanner - scan local repositories for code impact analysis.

This module provides CLI-level scanning of local Git repositories.
Used by `scopepilot codebase scan` command.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional


class CodebaseScanError(Exception):
    """Error during codebase scanning."""


def scan_local_repository(
    path: str,
    branch: Optional[str] = None,
    max_files: int = 5000,
    include_hidden: bool = False,
) -> dict:
    """Scan a local repository and return its structure metadata.

    Args:
        path: Path to the local repository.
        branch: Branch to scan (default: current branch or 'main').
        max_files: Maximum number of files to index.
        include_hidden: Whether to include dotfiles.

    Returns:
        dict with file_tree, language_breakdown, total_files, total_lines, etc.

    Raises:
        CodebaseScanError: If path doesn't exist or scanning fails.
    """
    repo_path = Path(path).resolve()
    if not repo_path.exists():
        raise CodebaseScanError(f"Path does not exist: {path}")
    if not repo_path.is_dir():
        raise CodebaseScanError(f"Not a directory: {path}")

    # Try to detect if it's a git repo
    git_root = _find_git_root(repo_path)
    is_git = git_root is not None

    # Determine branch
    if not branch and is_git:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=git_root or repo_path,
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if not branch:
        branch = "main"

    # Get commit SHA
    commit_sha = None
    if is_git:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=git_root or repo_path,
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                commit_sha = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Scan files
    files = []
    dirs = set()
    total_lines = 0
    total_bytes = 0
    language_bytes: dict[str, int] = {}

    # Language mapping by extension
    lang_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".jsx": "JavaScript", ".java": "Java", ".go": "Go", ".rs": "Rust",
        ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin",
        ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cs": "C#",
        ".sql": "SQL", ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
        ".xml": "XML", ".md": "Markdown", ".html": "HTML", ".css": "CSS",
        ".scss": "SCSS", ".less": "LESS", ".vue": "Vue", ".svelte": "Svelte",
        ".toml": "TOML", ".ini": "INI", ".cfg": "INI",
        ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
        ".dockerfile": "Dockerfile", "Dockerfile": "Dockerfile",
        ".proto": "Protobuf", ".graphql": "GraphQL", ".gql": "GraphQL",
    }

    # Directories to skip
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", ".env",
        "dist", "build", ".next", "target", "vendor", ".tox",
        ".egg-info", "site-packages", ".mypy_cache", ".pytest_cache",
        ".husky", ".github", ".vscode", ".idea",
    }

    scan_root = git_root or repo_path

    for root_str, dirnames, filenames in os.walk(str(scan_root)):
        # Skip hidden dirs unless include_hidden
        rel_root = Path(root_str).relative_to(scan_root)

        # Filter directories
        dirnames[:] = [
            d for d in dirnames
            if (include_hidden or not d.startswith("."))
            and d not in skip_dirs
        ]

        # Collect relative paths
        for fname in filenames:
            if not include_hidden and fname.startswith("."):
                continue
            if len(files) >= max_files:
                break

            rel_path = str(rel_root / fname) if str(rel_root) != "." else fname
            file_path = Path(root_str) / fname

            try:
                fsize = file_path.stat().st_size
                # Rough line estimate
                if fsize > 0:
                    # Only count text-like files (skip binaries)
                    _, ext = os.path.splitext(fname)
                    if ext in lang_map or not _is_binary_extension(ext):
                        files.append({
                            "path": rel_path,
                            "size": fsize,
                        })
                        if "/" in rel_path:
                            dirs.add("/".join(rel_path.split("/")[:-1]))

                        # Track by language
                        ext_lower = ext.lower()
                        if ext_lower in lang_map:
                            lang = lang_map[ext_lower]
                            language_bytes[lang] = language_bytes.get(lang, 0) + fsize
                        elif fname == "Dockerfile" or fname.startswith("Dockerfile."):
                            language_bytes["Dockerfile"] = language_bytes.get("Dockerfile", 0) + fsize

                        total_bytes += fsize
            except (OSError, PermissionError):
                continue

        if len(files) >= max_files:
            break

    return {
        "is_git": is_git,
        "git_root": str(git_root) if git_root else None,
        "branch": branch,
        "commit_sha": commit_sha,
        "file_tree": {
            "files": [f["path"] for f in files],
            "dirs": sorted(dirs),
        },
        "language_breakdown": language_bytes,
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "scanned_at": __import__("datetime").datetime.utcnow().isoformat(),
    }


def _find_git_root(path: Path) -> Optional[Path]:
    """Walk up directories to find the .git root."""
    for parent in [path] + list(path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _is_binary_extension(ext: str) -> bool:
    """Check if a file extension likely indicates a binary file."""
    binary_exts = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
        ".exe", ".dll", ".so", ".dylib", ".class", ".jar",
        ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
        ".woff", ".woff2", ".ttf", ".eot",
        ".pyc", ".pyo", ".pyd",
        ".db", ".sqlite", ".sqlite3",
        ".o", ".a", ".lib", ".obj",
    }
    return ext.lower() in binary_exts
