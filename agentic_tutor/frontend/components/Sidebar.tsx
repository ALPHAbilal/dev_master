"use client";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTutor } from "@/lib/session";
import type { Id, LadderTask } from "@/lib/api/types";
import Icon from "./Icon";
// Laid out like claude.ai's sidebar: the main action and every codebase carry a small
// icon, text starts 38px in, and the category title is small grey text with air above it.
// Quiet style: state is the text's tone. Grey is done, dark and bold is now, pale is later.
export default function Sidebar({
  collapsed,
  toggle,
  panel = null,
  openTask,
  add,
}: {
  collapsed: boolean;
  toggle(): void;
  panel?: Id | null; // the task whose panel is open
  openTask?(task: LadderTask): void;
  add?(): void;
}) {
  const tutor = useTutor(),
    router = useRouter(),
    path = usePathname();
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const now = tutor.snapshot?.where?.task_id;
  return (
    <nav className={"left" + (collapsed ? " collapsed" : "")} id="left">
      <button
        className="left-expand"
        id="leftExpand"
        title="Expand sidebar"
        onClick={toggle}
      >
        <Icon name="expand" size={16} />
      </button>
      <div className="left-inner" inert={collapsed}>
        <div className="left-head">
          <button
            className="collapse-btn"
            id="collapseLeft"
            title="Collapse"
            onClick={toggle}
          >
            <Icon name="collapse" />
          </button>
        </div>
        <div className="side-nav">
          <button
            className={"nav-row" + (path === "/scan" ? " on" : "")}
            id="importRow"
            onClick={add || (() => router.push("/scan"))}
          >
            <span className="ic">
              <Icon name="plus" size={16} />
            </span>
            <span className="lb">New codebase</span>
          </button>
        </div>
        <div className="side-label">Codebases</div>
        <div className="tree" id="tree">
          {tutor.workspaces.map((workspace) => {
            const active = workspace.id === tutor.workspaceId,
              open = active && !closed[workspace.id];
            const ladder = active ? tutor.snapshot?.ladder || [] : [];
            return (
              <div
                key={workspace.id}
                className={
                  "cb" +
                  (open ? " open" : "") +
                  (workspace.preparing === "running" ? " is-preparing" : "")
                }
              >
                <button
                  className={"cb-row" + (active ? " active" : "")}
                  aria-expanded={open}
                  onClick={async () => {
                    if (active)
                      setClosed((old) => ({ ...old, [workspace.id]: open }));
                    else {
                      await tutor.open(workspace.id).catch(tutor.report);
                      if (!openTask) router.push("/");
                    }
                  }}
                >
                  <span className="ic">
                    <Icon name="folder" size={16} />
                  </span>
                  <span className="cb-name">{workspace.name}</span>
                </button>
                <div className="units">
                  <div className="units-clip" inert={!open}>
                    {ladder.map((task) => (
                      <button
                        key={task.id}
                        className={
                          "unit task-row is-" +
                          task.status +
                          (task.id === now ? " now" : "") +
                          (task.id === panel ? " on" : "")
                        }
                        title={task.title}
                        aria-pressed={task.id === panel}
                        onClick={() => {
                          if (openTask) openTask(task);
                          else {
                            tutor.setPanelRequest(task.id);
                            router.push("/");
                          }
                        }}
                      >
                        <span className="u-name">{task.title}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
