"use client";
import { useLayoutEffect, useRef, useState } from "react";
import { useTutor } from "@/lib/session";
import { editKey } from "@/lib/editor";
import demo from "@/lib/api/demo.json";
import type { Ref } from "@/lib/api/types";
export default function Editor({
  attach,
}: {
  attach(ref: Ref, x: number, y: number): void;
}) {
  const tutor = useTutor();
  const [files, setFiles] = useState(() =>
    tutor.isStub
      ? demo.EDITOR_FILES.map((f, i) => ({ ...f, id: `editor-${i}` }))
      : [{ id: "editor-0", name: "untitled_1.py", content: "" }],
  );
  const [active, setActive] = useState("editor-0"),
    [renaming, setRenaming] = useState<string | null>(null),
    [saved, setSaved] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null),
    gutter = useRef<HTMLDivElement>(null),
    tabs = useRef<HTMLDivElement>(null),
    pendingSelection = useRef<{ start: number; end: number } | null>(null);
  const file = files.find((f) => f.id === active) || files[0];
  function update(content: string) {
    setFiles((old) =>
      old.map((f) => (f.id === file.id ? { ...f, content } : f)),
    );
    setSaved(false);
  }
  useLayoutEffect(() => {
    const selection = pendingSelection.current;
    if (selection && area.current) {
      area.current.setSelectionRange(selection.start, selection.end);
      pendingSelection.current = null;
    }
  }, [file.content]);
  useLayoutEffect(() => {
    setSaved(false);
    if (area.current) area.current.scrollTop = 0;
    if (gutter.current) gutter.current.scrollTop = 0;
    tabs.current
      ?.querySelector(".etab.on")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [active]);
  function rename(element: HTMLSpanElement) {
    const value = element.textContent?.trim();
    if (value)
      setFiles((old) =>
        old.map((f) => (f.id === renaming ? { ...f, name: value } : f)),
      );
    setRenaming(null);
  }
  return (
    <div className="code-editor">
      <div className="editor-tabs">
        <div
          className="editor-tabs-scroll"
          id="editorTabs"
          ref={tabs}
          onWheel={(e) => {
            if (e.deltaY) e.currentTarget.scrollLeft += e.deltaY;
          }}
        >
          {files.map((f) => (
            <div
              className={"etab" + (f.id === file.id ? " on" : "")}
              key={f.id}
            >
              <span
                className={"etab-name" + (renaming === f.id ? " editing" : "")}
                title="Double-click to rename"
                contentEditable={renaming === f.id}
                suppressContentEditableWarning
                onClick={() => {
                  setActive(f.id);
                  if (!renaming) area.current?.focus();
                }}
                onDoubleClick={(e) => {
                  setRenaming(f.id);
                  const el = e.currentTarget;
                  requestAnimationFrame(() => {
                    el.focus();
                    window.getSelection()?.selectAllChildren(el);
                  });
                }}
                onBlur={(e) => {
                  if (renaming === f.id) rename(e.currentTarget);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    e.currentTarget.blur();
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    e.currentTarget.textContent = f.name;
                    e.currentTarget.blur();
                  }
                }}
              >
                {f.name}
              </span>
              {files.length > 1 && (
                <button
                  className="etab-x"
                  title="Close"
                  onClick={() => {
                    const index = files.indexOf(f);
                    const remaining = files.filter((v) => v.id !== f.id);
                    setFiles(remaining);
                    if (file.id === f.id)
                      setActive(
                        remaining[Math.min(index, remaining.length - 1)].id,
                      );
                  }}
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
        <button
          className="etab-add"
          id="editorAddTab"
          title="New file"
          onClick={() => {
            let n = 1;
            while (files.some((f) => f.name === `untitled_${n}.py`)) n++;
            const id = crypto.randomUUID();
            setFiles((old) => [
              ...old,
              { id, name: `untitled_${n}.py`, content: "" },
            ]);
            setActive(id);
            area.current?.focus();
          }}
        >
          +
        </button>
      </div>
      <div className="editor-body">
        <div className="editor-gutter" id="editorGutter" ref={gutter}>
          {file.content.split("\n").map((_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>
        <textarea
          className="editor-area"
          id="editorArea"
          ref={area}
          spellCheck={false}
          wrap="off"
          value={file.content}
          onChange={(e) => update(e.target.value)}
          onScroll={(e) => {
            if (gutter.current)
              gutter.current.scrollTop = e.currentTarget.scrollTop;
          }}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing) return;
            const next = editKey(
              file.content,
              e.currentTarget.selectionStart,
              e.currentTarget.selectionEnd,
              e.key,
              e.shiftKey,
            );
            if (next) {
              e.preventDefault();
              pendingSelection.current = next;
              update(next.value);
            }
          }}
          onMouseUp={(e) => {
            const el = e.currentTarget,
              snippet = el.value.slice(el.selectionStart, el.selectionEnd);
            if (snippet.trim())
              attach(
                {
                  kind: "test",
                  label: file.name,
                  snippet,
                  source: { editor_id: file.id, text: file.content },
                },
                e.clientX,
                e.clientY,
              );
          }}
        />
      </div>
      <div className="run-row">
        <button
          className="btn primary"
          disabled={tutor.busy}
          onClick={async () => {
            if (await tutor.submit(file.content, file.name)) setSaved(true);
          }}
        >
          {saved ? "Submitted" : "Submit"}
        </button>
      </div>
    </div>
  );
}
