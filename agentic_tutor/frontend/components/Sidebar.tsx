"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTutor } from "@/lib/session";
import type { Unit } from "@/lib/api/types";
import Icon from "./Icon";
export default function Sidebar({
  collapsed,
  toggle,
  current,
  select,
  add,
  settings,
}: {
  collapsed: boolean;
  toggle(): void;
  current?: string;
  select?(unit: Unit): void;
  add?(): void;
  settings?(): void;
}) {
  const tutor = useTutor(),
    router = useRouter();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  return (
    <nav className={"left" + (collapsed ? " collapsed" : "")} id="left">
      <button
        className="left-expand"
        id="leftExpand"
        title="Expand sidebar"
        onClick={toggle}
      >
        <Icon name="rail" size={16} />
      </button>
      <div className="left-inner" inert={collapsed}>
        <div className="left-head">
          <button
            className="collapse-btn"
            id="collapseLeft"
            title="Collapse"
            onClick={toggle}
          >
            <Icon name="left" />
          </button>
        </div>
        <div className="side-nav">
          <button
            className="nav-row"
            id="importRow"
            title="Add a new codebase to scan"
            onClick={add || (() => router.push("/scan"))}
          >
            <span className="ic">
              <Icon name="plus" size={18} />
            </span>
            <span className="lb">Add new codebase</span>
          </button>
        </div>
        <div className="side-label">Codebases</div>
        <div className="tree" id="tree">
          {tutor.codebases.map((cb, i) => {
            const key = String(cb.id);
            const active =
              tutor.codebaseId == null
                ? tutor.isStub && i === 0
                : cb.id === tutor.codebaseId;
            const open = expanded[key] ?? active;
            const units = active ? tutor.snapshot?.units || [] : [];
            return (
              <div key={key} className={"cb" + (open ? " open" : "")}>
                <button
                  className="cb-row"
                  aria-expanded={open}
                  onClick={async () => {
                    setExpanded((old) => ({
                      ...old,
                      [key]: active ? !open : true,
                    }));
                    if (!active) await tutor.open(cb.id);
                  }}
                >
                  <span className="cb-caret">
                    <Icon size={13} />
                  </span>
                  <span className="cb-name">{cb.name}</span>
                  <span className="cb-count">
                    {units.filter((u) => u.state === "OWNED").length}/
                    {cb.unit_count}
                  </span>
                </button>
                <div className="units">
                  <div className="units-clip" inert={!open}>
                    {units.map((u) => (
                      <button
                        key={u.id}
                        className={
                          "unit " +
                          (current === u.slug
                            ? "current"
                            : u.state === "OWNED"
                              ? "owned"
                              : u.state === "QUEUED"
                                ? "locked"
                                : "")
                        }
                        disabled={u.state === "QUEUED"}
                        onClick={() => {
                          if (select) select(u);
                          else router.push("/");
                        }}
                      >
                        <span className="u-name">{u.slug}</span>
                        <span className="u-arrow">
                          <Icon size={13} />
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="left-foot">
          <button
            className="nav-row"
            id="settingsRow"
            title="Settings"
            onClick={settings}
          >
            <span className="ic">
              <Icon name="settings" size={18} />
            </span>
            <span className="lb">Settings</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
