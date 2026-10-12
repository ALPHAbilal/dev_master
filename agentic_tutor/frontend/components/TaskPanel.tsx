"use client";
import { useState } from "react";
import type { Box, Id, LadderIssue, LadderTask } from "@/lib/api/types";
import Icon from "./Icon";
export interface Selection {
  task_id: Id;
  issue_id: Id | null;
}
// Quiet style: no marks, no numbers. Dark text is proven or happening now, grey is
// done, pale is not open yet; a box not proven yet is a blank bar.
const HIDDEN = [64, 82, 52, 74, 90, 58];
function BoxRow({ box, open }: { box: Box; open(turn: number): void }) {
  if (box.ticked_at_turn == null || box.text == null)
    return (
      <div className="tp-item t-box">
        {box.text ?? (
          <span
            className="t-hidden"
            style={{ width: HIDDEN[box.number % HIDDEN.length] }}
          />
        )}
      </div>
    );
  return (
    <button className="tp-item t-box on" onClick={() => open(box.ticked_at_turn!)}>
      <span className="t-text">{box.text}</span>
    </button>
  );
}
function Issues({
  task,
  parent,
  focus,
  selection,
  select,
}: {
  task: LadderTask;
  parent: Id | null;
  focus: Id | null;
  selection: Selection | null;
  select(selection: Selection): void;
}) {
  const children = task.issues.filter((i) => i.parent_issue_id === parent);
  if (!children.length) return null;
  return (
    <div className="tp-children">
      {children.map((issue: LadderIssue) => (
        <div className="tp-child" key={issue.id}>
          <button
            className={
              "tp-item t-issue is-" +
              issue.status +
              (issue.id === focus ? " focus" : "") +
              (selection?.issue_id === issue.id ? " on" : "")
            }
            onClick={() => select({ task_id: task.id, issue_id: issue.id })}
          >
            <span className="t-text">{issue.title}</span>
          </button>
          <Issues
            task={task}
            parent={issue.id}
            focus={focus}
            selection={selection}
            select={select}
          />
        </div>
      ))}
    </div>
  );
}
function Group({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className={"tp-group" + (open ? " open" : "")}>
      <button
        className="tp-group-head"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        <span className="tp-chevron">
          <Icon size={13} />
        </span>
      </button>
      {open && children}
    </div>
  );
}
// The second sidebar: everything under one task. It opens when a task is clicked.
export default function TaskPanel({
  open,
  task,
  focus,
  selection,
  select,
  openTurn,
  openFile,
}: {
  open: boolean;
  task?: LadderTask;
  focus: Id | null;
  selection: Selection | null;
  select(selection: Selection): void;
  openTurn(task_id: Id, turn: number): void;
  openFile(path: string): void;
}) {
  const turn = (t: number) => task && openTurn(task.id, t);
  const locked = task?.status === "later";
  return (
    <aside
      className={"task-panel" + (open ? " open" : "")}
      aria-label="Task"
      inert={!open}
    >
      {task && (
        <div className={"tp-inner" + (locked ? " locked" : "")} key={task.id}>
          <button
            className="tp-title"
            onClick={() => !locked && select({ task_id: task.id, issue_id: null })}
          >
            {task.title}
          </button>
          <div className="tp-labels">
            <span className="tp-label">{task.tier}</span>
            {task.files.map((file) => (
              <button
                key={file}
                className="tp-label file"
                onClick={() => openFile(file)}
              >
                {file}
              </button>
            ))}
          </div>
          <div className="tp-scroll">
            <Group title="The job">
              <div className="tp-children">
                <div className="tp-child">
                  <BoxRow box={task.sheet.the_job_is_done} open={turn} />
                </div>
              </div>
            </Group>
            <Group title="Concepts">
              <div className="tp-children">
                {task.sheet.concepts.map((concept) => (
                  <div className="tp-child" key={concept.number}>
                    <div className={"tp-item t-cname" + (concept.checked ? " on" : "")}>
                      <span className="t-text">{concept.name}</span>
                    </div>
                    <div className="tp-children">
                      {concept.boxes.map((box) => (
                        <div className="tp-child" key={box.number}>
                          <BoxRow box={box} open={turn} />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Group>
            {task.issues.length > 0 && (
              <Group title="Issues">
                <Issues
                  task={task}
                  parent={null}
                  focus={focus}
                  selection={selection}
                  select={select}
                />
              </Group>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
