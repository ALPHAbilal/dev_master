"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useAuth } from "./auth";
import { createLiveApi } from "./api/live";
import { createStubApi, demoFiles } from "./api/stub";
import type {
  Api,
  Codebase,
  DriverState,
  Id,
  Ref,
  Snapshot,
  ToolEvent,
} from "./api/types";
const isStub = process.env.NEXT_PUBLIC_TRANSPORT !== "live";
function useSessionState() {
  const identity = useAuth();
  const api = useMemo<Api>(
    () =>
      isStub
        ? createStubApi()
        : createLiveApi(process.env.NEXT_PUBLIC_API_BASE || "", identity),
    [identity],
  );
  const [codebases, setCodebases] = useState<Codebase[]>([]),
    [driver, setDriver] = useState<DriverState | null>(null),
    [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [files, setFiles] = useState<Record<string, string>>(
      isStub ? demoFiles : {},
    ),
    [tools, setTools] = useState<ToolEvent[]>([]),
    [tokens, setTokens] = useState<
      Record<string, { thread_id?: string; turn_id: string; text: string }>
    >({});
  const [codebaseId, setCodebaseId] = useState<Id | null>(null);
  const workspaceRevision = useRef<number | null>(null),
    workspaceDocument = useRef<string | null>(null),
    revision = useRef<number | null>(null),
    activeJourney = useRef<Id | null>(null),
    inFlight = useRef(false),
    generation = useRef(0);
  const report = useCallback(
    (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
    [],
  );
  const refreshCodebases = useCallback(
    async () => setCodebases(await api.codebases()),
    [api],
  );
  const refresh = useCallback(
    async (id: Id, force = false) => {
      const epoch = generation.current;
      const update = await api.snapshot(id, force ? null : revision.current);
      if (activeJourney.current !== id || epoch !== generation.current) return;
      if (
        update.snapshot &&
        (revision.current == null || update.revision >= revision.current)
      ) {
        revision.current = update.revision;
        setSnapshot(update.snapshot);
        setTokens({});
        setTools([]);
      }
    },
    [api],
  );
  const adopt = useCallback(
    async (state: DriverState) => {
      if (activeJourney.current !== state.journey_id) {
        revision.current = null;
        setSnapshot(null);
      }
      activeJourney.current = state.journey_id;
      setDriver(state);
      await refresh(state.journey_id, true);
    },
    [refresh],
  );
  useEffect(() => {
    const epoch = ++generation.current;
    setDriver(null);
    setSnapshot(null);
    setFiles(isStub ? demoFiles : {});
    setCodebaseId(null);
    setTokens({});
    setTools([]);
    revision.current = null;
    activeJourney.current = null;
    void refreshCodebases().catch(report);
    if (isStub)
      void api
        .resume()
        .then((state) => {
          if (generation.current === epoch) return adopt(state);
        })
        .catch(report);
    else if (identity.user_id) {
      // Only cache routing state for this browser session, never credentials.
      try {
        const cached = sessionStorage.getItem(`tutor:${identity.user_id}`);
        if (cached) {
          const saved = JSON.parse(cached) as {
            codebaseId: Id;
            driver: DriverState;
          };
          if (saved.codebaseId != null && saved.driver?.journey_id != null)
            void api
              .open(saved.codebaseId)
              .then(async () => {
                if (generation.current !== epoch) return;
                setCodebaseId(saved.codebaseId);
                await adopt(saved.driver);
              })
              .catch(report);
        }
      } catch {
        /* Storage may be unavailable; the sidebar still opens sessions. */
      }
    }
    return () => {
      generation.current++;
    };
  }, [api, adopt, refreshCodebases, report]);
  useEffect(() => {
    if (!isStub && identity.user_id && driver && codebaseId != null) {
      try {
        sessionStorage.setItem(
          `tutor:${identity.user_id}`,
          JSON.stringify({ codebaseId, driver }),
        );
      } catch {
        /* storage is optional */
      }
    }
  }, [identity.user_id, driver, codebaseId]);
  useEffect(() => {
    if (!driver) return;
    const id = driver.journey_id;
    const stop = api.stream(id, {
      revision: () => {
        void refresh(id).catch(report);
      },
      tool: (event) => setTools((old) => [...old, event]),
      token: (event) =>
        setTokens((old) => {
          const key = `${event.thread_id || "main"}:${event.turn_id}`;
          return {
            ...old,
            [key]: { ...event, text: (old[key]?.text || "") + event.text },
          };
        }),
    });
    const timer = window.setInterval(() => {
      void refresh(id).catch(report);
    }, 4000);
    return () => {
      stop();
      clearInterval(timer);
    };
  }, [api, driver?.journey_id, refresh, report]);
  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      report(e);
      return undefined;
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  async function open(id: Id) {
    return run(async () => {
      await api.open(id);
      selectCodebase(id);
      workspaceRevision.current = null;
      await adopt(await api.resume());
      return true;
    });
  }
  function selectCodebase(id: Id) {
    setCodebaseId(id);
    setDriver(null);
    setSnapshot(null);
    revision.current = null;
    activeJourney.current = null;
    workspaceRevision.current = null;
  }
  async function answer(answer: string, refs: Ref[]) {
    return run(async () => {
      if (
        !driver ||
        driver.status !== "awaiting_learner" ||
        driver.unit_id == null ||
        !driver.turn_id ||
        !driver.axis ||
        driver.question == null
      )
        throw new Error("Open a lesson before answering.");
      await adopt(
        await api.answer(driver.journey_id, {
          turn_id: driver.turn_id,
          unit_id: driver.unit_id,
          axis: driver.axis,
          question: driver.question,
          answer,
          refs,
        }),
      );
      return true;
    });
  }
  async function aside(
    question: string,
    refs: Ref[],
    request_id: string,
    thread_id?: string,
    origin_message_id?: Id,
  ) {
    return run(async () => {
      if (!driver || driver.unit_id == null)
        throw new Error("Open a lesson before asking a side question.");
      const unit_id =
        snapshot?.aside_threads.find((t) => t.id === thread_id)?.unit_id ??
        driver.unit_id;
      const ack = await api.aside(driver.journey_id, {
        request_id,
        unit_id,
        question,
        refs,
        ...(thread_id ? { thread_id } : {}),
        ...(origin_message_id == null ? {} : { origin_message_id }),
      });
      await refresh(driver.journey_id, true);
      return ack;
    });
  }
  async function submit(content: string, name: string) {
    return run(async () => {
      if (
        workspaceRevision.current == null ||
        workspaceDocument.current !== name
      ) {
        const init = await api.init({
          target: name,
          document_id: name,
          display_name: name,
          language: name.endsWith(".py") ? "python" : "text",
        });
        workspaceRevision.current = init.workspace_revision;
        workspaceDocument.current = name;
      }
      const result = await api.workspace({
        content,
        expected_revision: workspaceRevision.current,
      });
      workspaceRevision.current = result.workspace_revision;
      return true;
    });
  }
  return {
    api,
    driver,
    snapshot,
    codebases,
    codebaseId,
    busy,
    error,
    files,
    tools,
    tokens,
    isStub,
    setFiles,
    setCodebaseId: selectCodebase,
    setError,
    report,
    refreshCodebases,
    adopt,
    open,
    answer,
    aside,
    submit,
    run,
  };
}
type Session = ReturnType<typeof useSessionState>;
const Context = createContext<Session | null>(null);
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const state = useSessionState();
  return <Context.Provider value={state}>{children}</Context.Provider>;
}
export function useTutor() {
  const value = useContext(Context);
  if (!value) throw new Error("SessionProvider is missing");
  return value;
}
