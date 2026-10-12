"use client";
import { useEffect, useState } from "react";
import { useTutor } from "@/lib/session";
import type { Attachment, Id, LadderTask } from "@/lib/api/types";
import Sidebar from "./Sidebar";
import TaskPanel, { type Selection } from "./TaskPanel";
import Icon from "./Icon";
import Map from "./Map";
import Conversation, { type Target } from "./Conversation";
import Editor from "./Editor";
import Codebase from "./Codebase";
import ErrorBanner from "./ErrorBanner";
export default function Tutor() {
  const tutor = useTutor();
  const [left, setLeft] = useState(true),
    [right, setRight] = useState(true),
    [width, setWidth] = useState<number | null>(null),
    [dragging, setDragging] = useState(false),
    [view, setView] = useState("map"),
    [tab, setTab] = useState("editor"),
    [selection, setSelection] = useState<Selection | null>(null),
    [panel, setPanel] = useState<Id | null>(null),
    [shown, setShown] = useState<Id | null>(null),
    [target, setTarget] = useState<Target | null>(null),
    [fileFocus, setFileFocus] = useState<{ path: string; at: number } | null>(null),
    [attachments, setAttachments] = useState<Attachment[]>([]),
    [pop, setPop] = useState<{
      attachment: Attachment;
      x: number;
      y: number;
    } | null>(null);
  const snapshot = tutor.snapshot,
    where = snapshot?.where;
  // The map follows the current task until the learner picks something else.
  useEffect(() => setSelection(null), [where?.task_id, tutor.workspaceId]);
  useEffect(() => setPanel(null), [tutor.workspaceId]);
  // A task clicked on the import page opens its panel here.
  const asked = tutor.panelRequest,
    setAsked = tutor.setPanelRequest;
  useEffect(() => {
    if (!asked) return;
    setPanel(asked);
    setShown(asked);
    setLeft(false);
    setAsked(null);
  }, [asked, setAsked]);
  // A click on a task folds the main sidebar into its rail and opens the task's
  // panel beside it. Unfolding the main sidebar closes the panel.
  function openTask(t: LadderTask) {
    setPanel(t.id);
    setShown(t.id);
    setLeft(false);
    if (t.status !== "later") setSelection({ task_id: t.id, issue_id: null });
  }
  function toggleLeft() {
    if (left) setLeft(false);
    else {
      setLeft(true);
      setPanel(null);
    }
  }
  const panelTask = snapshot?.ladder.find((t) => t.id === (panel ?? shown));
  const task =
    snapshot?.ladder.find((t) => t.id === selection?.task_id) ||
    snapshot?.ladder.find((t) => t.id === where?.task_id) ||
    snapshot?.ladder.findLast((t) => t.status === "done") ||
    snapshot?.ladder[0];
  const issue = selection?.issue_id
    ? task?.issues.find((i) => i.id === selection.issue_id)
    : null;
  // A file label in the task panel opens that file in the Codebase panel.
  function openFile(path: string) {
    setRight(true);
    setTab("codebase");
    setFileFocus({ path, at: Date.now() });
  }
  function openTurn(task_id: Id, turn: number) {
    setTarget({ task_id, turn, at: Date.now() });
    setView("conversation");
  }
  useEffect(() => {
    const close = (e: Event) => {
      if (e.type === "keydown" && (e as KeyboardEvent).key !== "Escape") return;
      if (e.target instanceof Element && e.target.closest(".ask-aside-pop"))
        return;
      setPop(null);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);
  function attach(attachment: Attachment, x: number, y: number) {
    setPop({
      attachment,
      x: Math.min(x + 8, window.innerWidth - 90),
      y: Math.max(35, y - 4),
    });
  }
  function add(attachment: Attachment) {
    setAttachments((old) => [...old, attachment]);
    setView("conversation");
  }
  return (
    <main className="tutor-screen">
      <button
        className={"reopen" + (!right ? " show" : "")}
        id="reopenRight"
        title="Show panel"
        onClick={() => setRight(true)}
      >
        <Icon name="left" size={13} />
      </button>
      <div
        className="shell"
        id="shell"
        style={{
          gridTemplateColumns: `${left ? 287 : 52}px ${panel ? 287 : 0}px minmax(0,1fr) ${right ? (width == null ? "30%" : width + "px") : "0px"}`,
          transition: dragging ? "none" : undefined,
          userSelect: dragging ? "none" : undefined,
        }}
      >
        <Sidebar
          collapsed={!left}
          toggle={toggleLeft}
          panel={panel}
          openTask={openTask}
        />
        <TaskPanel
          open={!!panel && !!panelTask}
          task={panelTask}
          focus={where?.task_id === panelTask?.id ? (where?.issue_id ?? null) : null}
          selection={selection}
          select={(s) => {
            setSelection(s);
            setTarget(null);
            setView("map");
          }}
          openTurn={openTurn}
          openFile={openFile}
        />
        <section className="mid">
          <div className="view-head">
            <div className="seg" id="midSeg">
              {["map", "conversation"].map((v) => (
                <button
                  key={v}
                  className={view === v ? "on" : ""}
                  onClick={() => {
                    setTarget(null);
                    setView(v);
                  }}
                >
                  {v === "map" ? "Map" : "Conversation"}
                </button>
              ))}
            </div>
          </div>
          <div className={"view" + (view === "map" ? " on" : "")} id="view-map">
            <Map task={task} issue={issue} openTurn={openTurn} />
          </div>
          <div
            className={"view" + (view === "conversation" ? " on" : "")}
            id="view-conversation"
          >
            <Conversation
              visible={view === "conversation"}
              target={target}
              attachments={attachments}
              setAttachments={setAttachments}
              attach={attach}
            />
          </div>
        </section>
        <aside
          className="right"
          id="right"
          style={{ visibility: right ? "visible" : "hidden" }}
          inert={!right}
        >
          <div
            className={"right-resizer" + (dragging ? " dragging" : "")}
            id="rightResizer"
            title="Drag to resize"
            onPointerDown={(e) => {
              setDragging(true);
              e.currentTarget.setPointerCapture(e.pointerId);
              e.preventDefault();
            }}
            onPointerMove={(e) => {
              if (dragging)
                setWidth(
                  Math.max(
                    300,
                    Math.min(
                      window.innerWidth * 0.72,
                      960,
                      window.innerWidth - e.clientX,
                    ),
                  ),
                );
            }}
            onPointerUp={(e) => {
              setDragging(false);
              e.currentTarget.releasePointerCapture(e.pointerId);
            }}
            onPointerCancel={() => setDragging(false)}
          />
          <div className="right-head">
            <button
              className="collapse-btn"
              id="collapseRight"
              title="Collapse"
              onClick={() => setRight(false)}
            >
              <Icon />
            </button>
            <div className="seg" id="rightSeg">
              {["editor", "codebase"].map((p) => (
                <button
                  key={p}
                  className={tab === p ? "on" : ""}
                  onClick={() => setTab(p)}
                >
                  {p === "editor" ? "Editor" : "Codebase"}
                </button>
              ))}
            </div>
          </div>
          <div
            className={"rview" + (tab === "editor" ? " on" : "")}
            id="rview-editor"
          >
            <Editor attach={attach} add={add} />
          </div>
          <div
            className={"rview" + (tab === "codebase" ? " on" : "")}
            id="rview-codebase"
          >
            <Codebase first={task?.files[0]} focus={fileFocus} attach={attach} />
          </div>
        </aside>
      </div>
      {pop && (
        <button
          className="ask-aside-pop"
          style={{ left: pop.x, top: pop.y }}
          onClick={() => {
            add(pop.attachment);
            setPop(null);
            window.getSelection()?.removeAllRanges();
          }}
        >
          <Icon name="plus" />
          Attach
        </button>
      )}
      <ErrorBanner />
    </main>
  );
}
