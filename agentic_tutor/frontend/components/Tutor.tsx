"use client";
import { useEffect, useRef, useState } from "react";
import { useTutor } from "@/lib/session";
import type { Ref } from "@/lib/api/types";
import Sidebar from "./Sidebar";
import Icon from "./Icon";
import Map from "./Map";
import Conversation from "./Conversation";
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
    [panel, setPanel] = useState("editor"),
    [slug, setSlug] = useState<string | null>(null),
    [refs, setRefs] = useState<Ref[]>([]),
    [expanded, setExpanded] = useState<string | null>(null),
    [attachment, setAttachment] = useState<{
      ref: Ref;
      x: number;
      y: number;
    } | null>(null);
  const settings = useRef<HTMLDialogElement>(null);
  const unit =
    tutor.snapshot?.units.find((u) => u.slug === slug) ||
    tutor.snapshot?.units.find((u) => u.id === tutor.driver?.unit_id) ||
    tutor.snapshot?.units[0];
  function openAside(id: string) {
    setExpanded(id);
    setView("conversation");
    window.history.replaceState(null, "", `#aside-${encodeURIComponent(id)}`);
    requestAnimationFrame(() =>
      document
        .getElementById(`aside-${id}`)
        ?.scrollIntoView({ block: "center" }),
    );
  }
  useEffect(() => {
    const hash = () => {
      if (window.location.hash.startsWith("#aside-")) {
        try {
          setExpanded(decodeURIComponent(window.location.hash.slice(7)));
          setView("conversation");
        } catch {
          /* malformed external hash */
        }
      }
    };
    hash();
    window.addEventListener("hashchange", hash);
    return () => window.removeEventListener("hashchange", hash);
  }, []);
  useEffect(() => {
    const close = (e: Event) => {
      if (e.type === "keydown" && (e as KeyboardEvent).key !== "Escape") return;
      if (e.target instanceof Element && e.target.closest(".ask-aside-pop"))
        return;
      setAttachment(null);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);
  function attach(ref: Ref, x: number, y: number) {
    setAttachment({
      ref,
      x: Math.min(x + 8, window.innerWidth - 90),
      y: Math.max(35, y - 4),
    });
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
          gridTemplateColumns: `${left ? 246 : 52}px minmax(0,1fr) ${right ? (width == null ? "36%" : width + "px") : "0px"}`,
          transition: dragging ? "none" : undefined,
          userSelect: dragging ? "none" : undefined,
        }}
      >
        <Sidebar
          collapsed={!left}
          toggle={() => setLeft(!left)}
          current={unit?.slug}
          select={(u) => {
            setSlug(u.slug);
            setView("map");
          }}
          settings={() => settings.current?.showModal()}
        />
        <section className="mid">
          <div className="view-head">
            <div className="seg" id="midSeg">
              {["map", "conversation"].map((v) => (
                <button
                  key={v}
                  className={view === v ? "on" : ""}
                  onClick={() => setView(v)}
                >
                  {v === "map" ? "Map" : "Conversation"}
                </button>
              ))}
            </div>
          </div>
          <div className={"view" + (view === "map" ? " on" : "")} id="view-map">
            <Map unit={unit} openAside={openAside} />
          </div>
          <div
            className={"view" + (view === "conversation" ? " on" : "")}
            id="view-conversation"
          >
            <Conversation
              refs={refs}
              setRefs={setRefs}
              expanded={expanded}
              openAside={openAside}
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
                  className={panel === p ? "on" : ""}
                  onClick={() => setPanel(p)}
                >
                  {p === "editor" ? "Editor" : "Codebase"}
                </button>
              ))}
            </div>
          </div>
          <div
            className={"rview" + (panel === "editor" ? " on" : "")}
            id="rview-editor"
          >
            <Editor attach={attach} />
          </div>
          <div
            className={"rview" + (panel === "codebase" ? " on" : "")}
            id="rview-codebase"
          >
            <Codebase unit={unit} attach={attach} />
          </div>
        </aside>
      </div>
      {attachment && (
        <button
          className="ask-aside-pop"
          style={{ left: attachment.x, top: attachment.y }}
          onClick={() => {
            setRefs((old) => [...old, attachment.ref]);
            setAttachment(null);
            setView("conversation");
            window.getSelection()?.removeAllRanges();
          }}
        >
          <Icon name="plus" />
          Attach
        </button>
      )}
      <ErrorBanner />
      <dialog className="settings" ref={settings}>
        <p>Settings</p>
        <button
          className="btn"
          onClick={async () => {
            if (tutor.driver?.unit_id != null)
              await tutor.run(async () => {
                await tutor.api.park(
                  tutor.driver!.journey_id,
                  tutor.driver!.unit_id!,
                );
                await tutor.adopt({ ...tutor.driver!, status: "parked" });
              });
          }}
        >
          Park lesson
        </button>
        <button
          className="btn"
          onClick={() =>
            tutor.run(async () => tutor.adopt(await tutor.api.resume()))
          }
        >
          Resume lesson
        </button>
        <button className="btn" onClick={() => settings.current?.close()}>
          Close
        </button>
      </dialog>
    </main>
  );
}
