import { Fragment } from "react";
import { useTutor } from "@/lib/session";
import type { Lifecycle, Unit } from "@/lib/api/types";
export function payload(event: Lifecycle): Record<string, unknown> {
  if (event.payload) return event.payload;
  try {
    return JSON.parse(event.payload_json || "{}");
  } catch {
    return {};
  }
}
export default function Map({
  unit,
  openAside,
}: {
  unit?: Unit;
  openAside(id: string): void;
}) {
  const { snapshot, driver } = useTutor();
  const descendants = new Set([String(unit?.id)]);
  // Walk only descendants of the selected unit; preserve lifecycle order.
  let grew = true;
  while (grew) {
    grew = false;
    for (const child of snapshot?.units || [])
      if (
        child.parent_id != null &&
        descendants.has(String(child.parent_id)) &&
        !descendants.has(String(child.id))
      ) {
        descendants.add(String(child.id));
        grew = true;
      }
  }
  const events =
    snapshot?.lifecycle.filter((e) => descendants.has(String(e.unit_id))) || [];
  const wording = snapshot?.axis_wording || {};
  function line(event: Lifecycle) {
    const p = payload(event),
      depth = Number(
        p.depth ??
          Math.max(
            0,
            (snapshot?.units.find((u) => String(u.id) === String(event.unit_id))
              ?.depth || 0) - (unit?.depth || 0),
          ),
      ),
      rail = <span className="fa">{"│  ".repeat(depth)}</span>;
    const text = String(p.text ?? p.title ?? p.reason ?? unit?.title ?? ""),
      axis = String(p.axis ?? event.axis ?? "");
    const at =
      axis && wording[axis] ? (
        <span className="dm">{"  ‹" + wording[axis] + "›"}</span>
      ) : null;
    const kind =
      (
        {
          teaching_presented: "learned",
          unit_distilled: "sealed",
          parent_resumed: "return",
          detour_started: "dive",
          gap_opened: "gap",
          journey_parked: "locked",
          journey_completed: "sealed",
        } as Record<string, string>
      )[event.event_type] || event.event_type;
    if (kind === "aside")
      return (
        <>
          {rail}
          <button
            className="story-aside"
            onClick={() => openAside(String(p.thread_id))}
          >
            <span className="dm">@ aside </span>
            <span className="cy">{String(p.title || "Side question")}</span>
          </button>
        </>
      );
    const labels: Record<string, [string, string, string]> = {
      learned: ["• ", "Learned   ", "dm"],
      proved: ["✓ ", "Proved    ", "o b"],
      shaky: ["~ ", "Almost    ", "od b"],
      gap: ["⚠ ", "Found a gap  ", "g b"],
      mechanism: ["⚙ ", "Reasoning off  ", "g b"],
      resolved: ["✓ ", "Cleared up — ", "gr b"],
      note: ["○ ", "Noted for later  ", "dm"],
      dive: [
        "↳ ",
        depth > 0 ? "Needed first — " : "Went to learn first — ",
        "g",
      ],
      sealed: ["★ ", "Sealed — you own ", "o"],
      return: ["↩ ", "Came back to ", "o b"],
      here: ["◉ ", "You are here — ", "o b"],
      why: ["↪ ", "", "dm i"],
      locked: ["", "", "dm"],
    };
    if (kind === "answer_evaluated") {
      const verdict = String(p.verdict);
      const l =
        labels[
          verdict === "SOLID" ? "proved" : verdict === "SHAKY" ? "shaky" : "gap"
        ];
      return (
        <>
          {rail}
          <span className={l[2]}>{l[0] + l[1]}</span>
          <span className="fg">{wording[axis] || axis}</span>
        </>
      );
    }
    const label = labels[kind];
    if (!label) return null;
    return (
      <span className={kind === "here" ? "hl-here" : undefined}>
        {rail}
        <span className={label[2]}>{label[0] + label[1]}</span>
        {kind === "resolved" ? (
          <s className="dm">{text}</s>
        ) : (
          <span
            className={
              ["return", "dive"].includes(kind)
                ? "cy b"
                : kind === "sealed"
                  ? "cy"
                  : ["note", "locked", "why"].includes(kind)
                    ? "dm"
                    : "fg"
            }
          >
            {text}
          </span>
        )}
        {at}
        {kind === "dive" && p.axis ? (
          <span className="dm">{"   (" + p.axis + ")"}</span>
        ) : null}
        {kind === "return" && p.resume_question ? (
          <span className="dm">
            {"\n" +
              "│  ".repeat(depth) +
              "   picking up: “" +
              p.resume_question +
              "”"}
          </span>
        ) : null}
      </span>
    );
  }
  const lines = events
    .map((event) => ({ id: event.id, rendered: line(event) }))
    .filter((e) => e.rendered);
  return (
    <div className="map-scroll">
      <div className="route-wrap">
        <pre className="unit-story" id="story">
          {!snapshot ? (
            <span className="dm">Open a codebase to begin.</span>
          ) : (
            <>
              {lines.map((e) => (
                <Fragment key={e.id}>
                  {e.rendered}
                  {"\n"}
                </Fragment>
              ))}
              {snapshot.semantic_nodes
                .filter((n) => String(n.unit_id) === String(unit?.id))
                .map((n) => (
                  <Fragment key={"node-" + n.id}>
                    <span
                      className={
                        n.status === "disproved"
                          ? "gr"
                          : n.kind === "mechanism" || n.kind === "misconception"
                            ? "g"
                            : "fg"
                      }
                    >
                      {n.status === "disproved" ? "✓ Cleared up — " : "• "}
                      {String(n.summary || n.title || n.text || n.label || "")}
                    </span>
                    {"\n"}
                  </Fragment>
                ))}
              {!events.some((e) => e.event_type === "here") &&
                driver &&
                driver.unit_id === unit?.id && (
                  <span className="hl-here">
                    <span className="o b">◉ You are here</span> —{" "}
                    {driver.question || driver.reason}
                  </span>
                )}
            </>
          )}
        </pre>
      </div>
    </div>
  );
}
