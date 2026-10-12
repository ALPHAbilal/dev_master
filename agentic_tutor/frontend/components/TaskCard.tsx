"use client";
import type { Box, LadderTask } from "@/lib/api/types";
// Quiet style, like the task panel: no marks, no numbers; a box not proven yet is a blank bar.
const HIDDEN = [64, 82, 52, 74, 90, 58];
function BoxLine({ box, sub }: { box: Box; sub?: boolean }) {
  return (
    <p className={"tc-item" + (sub ? " sub" : "") + (box.ticked_at_turn != null ? " on" : "")}>
      {box.text ?? (
        <span
          className="t-hidden"
          style={{ width: HIDDEN[box.number % HIDDEN.length] }}
        />
      )}
    </p>
  );
}
// The task card of the import page. It never shows the answer key.
export default function TaskCard({ task }: { task: LadderTask }) {
  return (
    <div className={"task-card" + (task.status === "later" ? " locked" : "")}>
      <div className="tc-title">{task.title}</div>
      <div className="tp-labels">
        <span className="tp-label">{task.tier}</span>
        {task.files.map((file) => (
          <span key={file} className="tp-label file">
            {file}
          </span>
        ))}
      </div>
      <div className="tc-sec">The job</div>
      <BoxLine box={task.sheet.the_job_is_done} />
      <div className="tc-sec">Concepts</div>
      {task.sheet.concepts.map((concept) => (
        <div className="tc-concept" key={concept.number}>
          <p className={"tc-item" + (concept.checked ? " on" : "")}>{concept.name}</p>
          {concept.boxes.map((box) => (
            <BoxLine key={box.number} box={box} sub />
          ))}
        </div>
      ))}
    </div>
  );
}
