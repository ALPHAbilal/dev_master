"use client";
import { useEffect, useState } from "react";
import { useTutor } from "@/lib/session";
import type { Attachment } from "@/lib/api/types";
import Icon from "./Icon";
type TreeNode = {
  name: string;
  path: string;
  children: TreeNode[];
  file: boolean;
};
function tree(paths: string[]): TreeNode[] {
  const root: TreeNode[] = [];
  for (const path of paths) {
    let level = root;
    path.split("/").forEach((name, i, parts) => {
      let node = level.find((n) => n.name === name);
      if (!node) {
        node = {
          name,
          path: parts.slice(0, i + 1).join("/"),
          file: i === parts.length - 1,
          children: [],
        };
        level.push(node);
      }
      level = node.children;
    });
  }
  return root;
}
function ExplorerRow({
  node,
  depth,
  active,
  open,
}: {
  node: TreeNode;
  depth: number;
  active: string;
  open(path: string): void;
}) {
  const [closed, setClosed] = useState(false);
  return (
    <div
      className={
        node.file ? "ex-file" : "ex-folder" + (closed ? " closed" : "")
      }
    >
      <div
        className={"ex-row" + (node.file && node.path === active ? " on" : "")}
        role="button"
        tabIndex={0}
        style={{ paddingLeft: 10 + depth * 14 }}
        onClick={() => (node.file ? open(node.path) : setClosed(!closed))}
        onKeyDown={(e) => {
          if (e.key === "Enter")
            node.file ? open(node.path) : setClosed(!closed);
        }}
        onMouseEnter={(e) => {
          const clip =
              e.currentTarget.querySelector<HTMLElement>(".ex-name-clip"),
            name = e.currentTarget.querySelector<HTMLElement>(".ex-name");
          if (clip && name) {
            const over = name.scrollWidth - clip.clientWidth;
            if (over > 2) {
              name.style.setProperty("--shift", `-${over + 6}px`);
              name.style.setProperty(
                "--dur",
                `${Math.max(1.6, (over + 6) / 40)}s`,
              );
              name.classList.add("scrolling");
            }
          }
        }}
        onMouseLeave={(e) =>
          e.currentTarget
            .querySelector(".ex-name")
            ?.classList.remove("scrolling")
        }
      >
        <span className="ex-caret2">
          <Icon size={13} />
        </span>
        <span className="ex-svg">
          <Icon name={node.file ? "file" : "folder"} />
        </span>
        <span className="ex-name-clip">
          <span className="ex-name">{node.name}</span>
        </span>
      </div>
      {!node.file && (
        <div className="ex-children">
          {node.children.map((child) => (
            <ExplorerRow
              key={child.path}
              node={child}
              depth={depth + 1}
              active={active}
              open={open}
            />
          ))}
        </div>
      )}
    </div>
  );
}
export default function Codebase({
  first,
  focus,
  attach,
}: {
  first?: string;
  focus?: { path: string; at: number } | null;
  attach(attachment: Attachment, x: number, y: number): void;
}) {
  const { files, loadFile } = useTutor(),
    [selected, setSelected] = useState<string | null>(null),
    [collapsed, setCollapsed] = useState(false);
  const paths = Object.keys(files);
  const path =
      selected || (first && first in files ? first : paths[0]) || "",
    source = files[path],
    lines = source?.split("\n") || [];
  useEffect(() => {
    if (path && files[path] == null) void loadFile(path);
  }, [path, files, loadFile]);
  useEffect(() => {
    if (focus) setSelected(focus.path);
  }, [focus]);
  function select(e: React.MouseEvent) {
    const selection = window.getSelection();
    if (!selection?.toString().trim()) return;
    const a =
        selection.anchorNode?.parentElement?.closest<HTMLElement>(
          "[data-line]",
        ),
      b =
        selection.focusNode?.parentElement?.closest<HTMLElement>("[data-line]");
    if (
      !a ||
      !b ||
      !e.currentTarget.contains(a) ||
      !e.currentTarget.contains(b)
    )
      return;
    const lo = Math.min(Number(a.dataset.line), Number(b.dataset.line)),
      hi = Math.max(Number(a.dataset.line), Number(b.dataset.line));
    attach(
      {
        kind: "repository_code",
        label: `${path} · lines ${lo} to ${hi}`,
        text: lines.slice(lo - 1, hi).join("\n"),
        source: { file: path, first_line: lo, last_line: hi },
      },
      e.clientX,
      e.clientY,
    );
  }
  return (
    <>
      <div
        className={"explorer" + (collapsed ? " collapsed" : "")}
        id="cbExplorer"
      >
        <div
          className="explorer-head"
          id="cbExplorerHead"
          role="button"
          tabIndex={0}
          onClick={() => setCollapsed(!collapsed)}
          onKeyDown={(e) => {
            if (e.key === "Enter") setCollapsed(!collapsed);
          }}
        >
          <span className="ex-caret">
            <Icon size={10} />
          </span>
          <span className="ex-label">Explorer</span>
        </div>
        <div className="ex-tree" id="cbTree">
          {tree(paths).map((node) => (
            <ExplorerRow
              key={node.path}
              node={node}
              depth={0}
              active={path}
              open={setSelected}
            />
          ))}
        </div>
      </div>
      <div className="cb-code">
        <div className="cb-scroll">
          <div className="codebase" id="codebase" onMouseUp={select}>
            {source == null ? (
              <span className="file-sep">
                {path ? "Loading…" : "No files yet."}
              </span>
            ) : (
              lines.map((line, i) => (
                <div className="code-line" key={i} data-line={i + 1}>
                  <span className="ln">{i + 1}</span>
                  <span className="code">{line || " "}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}
