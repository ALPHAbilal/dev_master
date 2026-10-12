"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTutor } from "@/lib/session";
import type {
  Id,
  LadderTask,
  PreparingEvents,
  PreparingStep,
} from "@/lib/api/types";
import Sidebar from "./Sidebar";
import Icon from "./Icon";
import ErrorBanner from "./ErrorBanner";
import TaskCard from "./TaskCard";
// The crafting line, in the order it runs (LEGO.md §13).
const STEPS: [PreparingStep, string][] = [
  ["copying", "copying the repository"],
  ["concepts", "finding the concepts"],
  ["tasks", "writing the tasks"],
  ["ordering", "ordering the tasks"],
];
const GHOSTS = [96, 132, 78];
type Written = PreparingEvents["task"];
// Quiet style: no marks, no motion. A step is grey once done, dark while it runs,
// pale while it waits; a task appears in the list as soon as it is written.
export default function Scan() {
  const tutor = useTutor(),
    router = useRouter();
  const [left, setLeft] = useState(true),
    [url, setUrl] = useState(""),
    [importing, setImporting] = useState(false),
    [workspace, setWorkspace] = useState<{
      id: Id;
      name: string;
      url: string;
    } | null>(null),
    [steps, setSteps] = useState<
      Partial<Record<PreparingStep, PreparingEvents["step"]>>
    >({}),
    [concepts, setConcepts] = useState<PreparingEvents["concept"][]>([]),
    [tasks, setTasks] = useState<Written[]>([]),
    [status, setStatus] = useState<"running" | "ready" | "failed">("running"),
    [failure, setFailure] = useState<PreparingEvents["failed"] | null>(null),
    [detail, setDetail] = useState<LadderTask | null>(null);
  const stop = useRef<(() => void) | null>(null),
    active = useRef(true),
    lock = useRef(false);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      stop.current?.();
    };
  }, []);
  function watch(id: Id) {
    stop.current?.();
    setSteps({});
    setConcepts([]);
    setTasks([]);
    setStatus("running");
    setFailure(null);
    stop.current = tutor.api.preparing(id, {
      step: (e) => active.current && setSteps((old) => ({ ...old, [e.name]: e })),
      concept: (e) => active.current && setConcepts((old) => [...old, e]),
      task: (e) =>
        active.current &&
        setTasks((old) => (old.some((t) => t.id === e.id) ? old : [...old, e])),
      ready: () => {
        if (!active.current) return;
        setStatus("ready");
        void tutor.refreshWorkspaces().catch(tutor.report);
      },
      failed: (e) => {
        if (!active.current) return;
        setStatus("failed");
        setFailure(e);
      },
    });
  }
  async function importRepository() {
    const value = url.trim();
    if (!value || lock.current) return;
    lock.current = true;
    setImporting(true);
    tutor.setError("");
    try {
      if (!/^https:\/\/\S+$/.test(value))
        throw new Error("Use an https:// repository URL.");
      const name =
        value
          .replace(/\/+$/, "")
          .split("/")
          .pop()
          ?.replace(/\.git$/, "") || "repository";
      const { workspace_id } = await tutor.api.importRepository({
        name,
        git_url: value,
      });
      await tutor.refreshWorkspaces();
      if (!active.current) return;
      setWorkspace({ id: workspace_id, name, url: value });
      watch(workspace_id);
    } catch (error) {
      tutor.report(error);
    } finally {
      lock.current = false;
      if (active.current) setImporting(false);
    }
  }
  async function enter(start: boolean) {
    if (!workspace) return;
    const ok = await tutor.run(async () => {
      if (start) await tutor.api.start(workspace.id);
      await tutor.open(workspace.id);
      return true;
    });
    if (ok) router.push("/");
  }
  function reset() {
    if (lock.current) return;
    stop.current?.();
    stop.current = null;
    setWorkspace(null);
    setDetail(null);
  }
  const ghosts =
    status === "running" && steps.tasks?.state !== "done" ? GHOSTS : [];
  return (
    <main className="scan-screen">
      <div className="app">
        <Sidebar collapsed={!left} toggle={() => setLeft(!left)} add={reset} />
        <div className="canvas">
          <div className="stage">
            <div
              className={"import-view" + (workspace ? " gone" : "")}
              id="importView"
              inert={!!workspace}
            >
              <div className="import-card">
                <div className="import-field">
                  <input
                    id="importInput"
                    spellCheck={false}
                    aria-label="Repository URL"
                    placeholder="https://github.com/you/your-repository"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void importRepository();
                      }
                    }}
                  />
                </div>
                <button
                  className="import-go"
                  id="importGo"
                  disabled={!url.trim() || importing}
                  onClick={() => void importRepository()}
                >
                  Import
                </button>
              </div>
            </div>
            <div
              id="scanView"
              className={workspace ? "on" : ""}
              inert={!workspace || !!detail}
            >
              <div className="title-row">
                <span className="fn" id="scanFn">
                  {workspace?.name}
                </span>
              </div>
              <div className="boxes">
                <div className="box" id="logBox">
                  <div className="box-label">Preparing</div>
                  <div className="log-list" id="logList">
                    {STEPS.map(([name, words]) => (
                      <div
                        className={"step " + (steps[name]?.state ?? "waiting")}
                        key={name}
                      >
                        {words}
                      </div>
                    ))}
                    {concepts.map((c) => (
                      <div className="step concept" key={c.number}>
                        {c.name}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="box bag-box">
                  <div className="box-label">Tasks</div>
                  <div className="task-list" id="bag">
                    {tasks.map((t) => (
                      <button
                        key={t.id}
                        className="task-line"
                        onClick={() =>
                          workspace &&
                          void tutor.api
                            .task(workspace.id, t.id)
                            .then((found) => active.current && setDetail(found))
                            .catch(tutor.report)
                        }
                      >
                        {t.title}
                      </button>
                    ))}
                    {ghosts.map((w, i) => (
                      <div key={"ghost-" + i} className="task-line ghost">
                        <span className="t-hidden" style={{ width: w }} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="gen-row" id="genRow">
                {status === "ready" ? (
                  <button className="req-go" onClick={() => void enter(true)}>
                    Start the first task
                  </button>
                ) : status === "failed" ? (
                  <div className="req">
                    <span className="req-unit">
                      Preparing stopped at{" "}
                      {STEPS.find(([name]) => name === failure?.step)?.[1] ||
                        "a step"}
                      : {failure?.error}
                    </span>
                    <button
                      className="req-go"
                      onClick={() => workspace && watch(workspace.id)}
                    >
                      Try again
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
            <div
              className={"detail" + (detail ? " on" : "")}
              id="detail"
              inert={!detail}
            >
              <div className="detail-bar">
                <button
                  className="back"
                  id="backBtn"
                  onClick={() => setDetail(null)}
                >
                  <Icon name="left" />
                  Back
                </button>
                {detail && detail.status !== "later" && (
                  <button
                    className="open-lesson"
                    id="openLesson"
                    onClick={() => void enter(false)}
                  >
                    Open task
                  </button>
                )}
              </div>
              <div className="detail-body" id="detailBody">
                {detail && <TaskCard key={detail.id} task={detail} />}
              </div>
            </div>
          </div>
        </div>
      </div>
      <ErrorBanner />
    </main>
  );
}
