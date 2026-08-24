"""Deterministic Python code-structure extraction.

Parses a source file into structural nodes (module, class, function, method) with exact
line ranges and ``contains`` edges. This is the parser-provenance producer for the
semantic graph. It authors no concepts and makes no learning judgment — only facts the
Python AST can establish. Ranges are the parser's canonical ranges and are never cropped
to a learning unit (proposal §7).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ValidationError


@dataclass(frozen=True, slots=True)
class StructuralNode:
    kind: str          # module | class | function | method
    name: str
    qualname: str      # dotted path, e.g. "ConfigLoader.load"
    file: str
    lo: int
    hi: int


@dataclass(frozen=True, slots=True)
class StructuralEdge:
    from_qualname: str
    to_qualname: str
    relationship: str  # "contains"


@dataclass(frozen=True, slots=True)
class StructureExtraction:
    nodes: tuple[StructuralNode, ...] = ()
    edges: tuple[StructuralEdge, ...] = ()


class StructureExtractor:
    """Extract module/class/function/method structure from one Python file."""

    def __init__(self, codebase_root: Path) -> None:
        self.codebase_root = codebase_root.resolve()

    def extract(self, file_relpath: str) -> StructureExtraction:
        candidate = (self.codebase_root / file_relpath).resolve()
        if candidate != self.codebase_root and self.codebase_root not in candidate.parents:
            raise ValidationError("source path escapes the configured codebase root")
        if not candidate.is_file():
            raise ValidationError(f"source file is unavailable: {file_relpath}")
        source = candidate.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            raise ValidationError(f"cannot parse {file_relpath}: {error}") from error

        total_lines = len(source.splitlines()) or 1
        module = StructuralNode("module", file_relpath, file_relpath, file_relpath, 1, total_lines)
        nodes: list[StructuralNode] = [module]
        edges: list[StructuralEdge] = []
        self._walk(tree.body, parent=module, file_relpath=file_relpath, nodes=nodes, edges=edges)
        return StructureExtraction(tuple(nodes), tuple(edges))

    def _walk(self, body: list[ast.stmt], *, parent: StructuralNode, file_relpath: str,
              nodes: list[StructuralNode], edges: list[StructuralEdge]) -> None:
        for statement in body:
            if isinstance(statement, ast.ClassDef):
                node = self._node("class", statement, parent, file_relpath)
                nodes.append(node)
                edges.append(StructuralEdge(parent.qualname, node.qualname, "contains"))
                self._walk(statement.body, parent=node, file_relpath=file_relpath, nodes=nodes, edges=edges)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if parent.kind == "class" else "function"
                node = self._node(kind, statement, parent, file_relpath)
                nodes.append(node)
                edges.append(StructuralEdge(parent.qualname, node.qualname, "contains"))
                # Nested defs are captured under their enclosing function.
                self._walk(statement.body, parent=node, file_relpath=file_relpath, nodes=nodes, edges=edges)

    @staticmethod
    def _node(kind: str, statement: ast.stmt, parent: StructuralNode, file_relpath: str) -> StructuralNode:
        name = getattr(statement, "name")
        qualname = name if parent.kind == "module" else f"{parent.qualname}.{name}"
        lo = int(statement.lineno)
        hi = int(getattr(statement, "end_lineno", statement.lineno) or statement.lineno)
        return StructuralNode(kind, name, qualname, file_relpath, lo, hi)


def reconcile_range(unit_lo: int, unit_hi: int, node_lo: int, node_hi: int) -> str | None:
    """Classify how a learning unit's range relates to a structural node's range.

    Returns one of ``contains`` (the unit fully contains the node), ``focuses_on``
    (the unit sits inside a larger node — e.g. a method the unit only partly covers),
    ``overlaps`` (partial overlap), or ``None`` when the ranges are disjoint. Neither
    range is ever rewritten to match the other (proposal §7).
    """
    if node_hi < unit_lo or unit_hi < node_lo:
        return None
    if unit_lo <= node_lo and node_hi <= unit_hi:
        return "contains"
    if node_lo <= unit_lo and unit_hi <= node_hi:
        return "focuses_on"
    return "overlaps"
