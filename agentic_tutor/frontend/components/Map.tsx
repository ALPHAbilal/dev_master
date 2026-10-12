import { Fragment } from "react";
import { useTutor } from "@/lib/session";
import type { Id, LadderIssue, LadderTask, StoryKind, StoryLine } from "@/lib/api/types";
// Every kind of story line: its mark, its words, and their colors.
const LABELS: Record<StoryKind, [string, string, string, string]> = {
  started: ["• ", "Started  ", "dm", "fg"],
  did: ["✓ ", "Did  ", "o b", "fg"],
  ticked: ["☑ ", "", "o b", "fg"],
  almost: ["~ ", "Almost  ", "od b", "fg"],
  found_a_gap: ["⚠ ", "Found a gap  ", "g b", "fg"],
  went_to_learn_first: ["↳ ", "Went to learn first — ", "g", "cy b"],
  needed_first: ["↳ ", "Needed first — ", "g", "cy b"],
  saved_for_later: ["○ ", "Saved for later  ", "dm", "dm"],
  put_on_hold: ["‖ ", "Put on hold — ", "dm", "dm"],
  picked_up: ["↳ ", "Picked up — ", "g", "cy b"],
  cleared: ["★ ", "Cleared — ", "o", "cy"],
  already_knew: ["✕ ", "Already knew it — ", "o", "cy"],
  came_back: ["↩ ", "Came back to ", "o b", "cy b"],
  done: ["★ ", "Done — ", "o b", "cy b"],
};
// An issue and every issue opened inside it.
function subtree(issues: LadderIssue[], root: Id): Set<Id> {
  const ids = new Set([root]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const issue of issues)
      if (
        issue.parent_issue_id != null &&
        ids.has(issue.parent_issue_id) &&
        !ids.has(issue.id)
      ) {
        ids.add(issue.id);
        grew = true;
      }
  }
  return ids;
}
export default function Map({
  task,
  issue,
  openTurn,
}: {
  task?: LadderTask;
  issue?: LadderIssue | null;
  openTurn(task_id: Id, turn: number): void;
}) {
  const { snapshot } = useTutor();
  const where = snapshot?.where;
  const inside = issue ? subtree(task?.issues || [], issue.id) : null;
  const lines =
    snapshot?.story.filter(
      (l) =>
        l.task_id === task?.id &&
        (!inside || (l.issue_id != null && inside.has(l.issue_id))),
    ) || [];
  const base = inside && lines.length ? Math.min(...lines.map((l) => l.depth)) : 0;
  const rail = (depth: number) => (
    <span className="fa">{"│  ".repeat(Math.max(0, depth - base))}</span>
  );
  function line(l: StoryLine) {
    const [mark, words, markClass, textClass] = LABELS[l.kind];
    return (
      <>
        {rail(l.depth)}
        <button
          className="story-line"
          title="Open this turn in the conversation"
          onClick={() => openTurn(l.task_id, l.turn)}
        >
          <span className={markClass}>{mark + words}</span>
          <span className={textClass}>{l.text}</span>
        </button>
        {l.kind === "came_back" && l.picking_up ? (
          <>
            {"\n"}
            {rail(l.depth)}
            <span className="dm">{`   picking up: “${l.picking_up}”`}</span>
          </>
        ) : null}
      </>
    );
  }
  const here =
    where &&
    task &&
    where.task_id === task.id &&
    (!inside || (where.issue_id != null && inside.has(where.issue_id)));
  return (
    <div className="map-scroll">
      <div className="route-wrap">
        <pre className="unit-story" id="story">
          {!snapshot ? (
            <span className="dm">Open a codebase to begin.</span>
          ) : !task || task.status === "later" ? (
            <span className="dm">This task has not started yet.</span>
          ) : (
            <>
              {lines.map((l) => (
                <Fragment key={l.id}>
                  {line(l)}
                  {"\n"}
                </Fragment>
              ))}
              {here && (
                <>
                  {rail(where.depth)}
                  <span className="hl-here">
                    <span className="o b">◉ You are here — </span>
                    <span className="fg">{where.you_are_here}</span>
                  </span>
                </>
              )}
            </>
          )}
        </pre>
      </div>
    </div>
  );
}
