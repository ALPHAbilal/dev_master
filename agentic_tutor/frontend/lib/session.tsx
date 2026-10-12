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
import { createStubApi } from "./api/stub";
import type { Api, Attachment, Id, Snapshot, Workspace } from "./api/types";
const isStub = process.env.NEXT_PUBLIC_TRANSPORT !== "live";
// What the tutor is doing right now, before its reply is in the snapshot.
export interface Live {
  task_id: Id;
  turn: number;
  text: string;
  tools: string[];
}
function useSessionState() {
  const identity = useAuth();
  const api = useMemo<Api>(
    () =>
      isStub
        ? createStubApi()
        : createLiveApi(process.env.NEXT_PUBLIC_API_BASE || "", identity),
    [identity],
  );
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]),
    [workspaceId, setWorkspaceId] = useState<Id | null>(null),
    [snapshot, setSnapshot] = useState<Snapshot | null>(null),
    [files, setFiles] = useState<Record<string, string | null>>({}),
    [live, setLive] = useState<Record<string, Live>>({}),
    // A task to open in the main screen's task panel, asked for from another page.
    [panelRequest, setPanelRequest] = useState<Id | null>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const revision = useRef<number | null>(null),
    active = useRef<Id | null>(null),
    inFlight = useRef(false),
    loading = useRef(new Set<string>()),
    generation = useRef(0);
  const report = useCallback(
    (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
    [],
  );
  const refreshWorkspaces = useCallback(
    async () => setWorkspaces(await api.workspaces()),
    [api],
  );
  const refresh = useCallback(
    async (id: Id, force = false) => {
      const epoch = generation.current;
      const update = await api.snapshot(id, force ? null : revision.current);
      if (active.current !== id || epoch !== generation.current) return;
      if (
        update.snapshot &&
        (revision.current == null || update.revision >= revision.current)
      ) {
        revision.current = update.revision;
        setSnapshot(update.snapshot);
      }
    },
    [api],
  );
  const open = useCallback(
    async (id: Id) => {
      if (active.current === id) return;
      active.current = id;
      revision.current = null;
      setWorkspaceId(id);
      setSnapshot(null);
      setLive({});
      setFiles({});
      await refresh(id, true);
      const paths = await api.files(id);
      if (active.current === id)
        setFiles(Object.fromEntries(paths.map((p) => [p, null])));
    },
    [api, refresh],
  );
  useEffect(() => {
    const epoch = ++generation.current;
    active.current = null;
    revision.current = null;
    setWorkspaceId(null);
    setSnapshot(null);
    setFiles({});
    setLive({});
    void refreshWorkspaces().catch(report);
    if (isStub) void open("demo").catch(report);
    else if (identity.user_id) {
      // Only routing state is cached for this browser session, never credentials.
      try {
        const cached = sessionStorage.getItem(`tutor:${identity.user_id}`);
        if (cached && generation.current === epoch)
          void open(cached).catch(report);
      } catch {
        /* Storage may be unavailable; the sidebar still opens workspaces. */
      }
    }
    return () => {
      generation.current++;
    };
  }, [api, open, refreshWorkspaces, report, identity.user_id]);
  useEffect(() => {
    if (isStub || !identity.user_id || workspaceId == null) return;
    try {
      sessionStorage.setItem(`tutor:${identity.user_id}`, workspaceId);
    } catch {
      /* storage is optional */
    }
  }, [identity.user_id, workspaceId]);
  useEffect(() => {
    if (workspaceId == null) return;
    const id = workspaceId;
    const key = (task_id: Id, turn: number) => `${task_id}:${turn}`;
    const stop = api.stream(id, {
      revision: () => {
        void refresh(id).catch(report);
      },
      tool: (event) =>
        setLive((old) => {
          const k = key(event.task_id, event.turn),
            was = old[k] || { ...event, text: "", tools: [] };
          return { ...old, [k]: { ...was, tools: [...was.tools, event.doing] } };
        }),
      tutor: (event) =>
        setLive((old) => {
          const k = key(event.task_id, event.turn),
            was = old[k] || { ...event, text: "", tools: [] };
          return { ...old, [k]: { ...was, text: was.text + event.text } };
        }),
    });
    const timer = window.setInterval(() => {
      void refresh(id).catch(report);
    }, 4000);
    return () => {
      stop();
      clearInterval(timer);
    };
  }, [api, workspaceId, refresh, report]);
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
  async function send(text: string, attachments: Attachment[], id: string) {
    return run(async () => {
      if (workspaceId == null || !snapshot?.where)
        throw new Error("Open a task before writing to the tutor.");
      await api.send(workspaceId, {
        client_message_id: id,
        text,
        attachments,
      });
      await refresh(workspaceId);
      return true;
    });
  }
  async function stop() {
    if (workspaceId == null) return;
    try {
      await api.stop(workspaceId);
    } catch (e) {
      report(e);
    }
  }
  async function loadFile(path: string) {
    if (workspaceId == null || files[path] != null) return;
    const id = workspaceId,
      key = `${id}:${path}`;
    if (loading.current.has(key)) return;
    loading.current.add(key);
    try {
      const file = await api.file(id, path);
      if (active.current === id)
        setFiles((old) => ({ ...old, [file.path]: file.text }));
    } catch (e) {
      report(e);
    } finally {
      loading.current.delete(key);
    }
  }
  return {
    api,
    isStub,
    workspaces,
    workspaceId,
    snapshot,
    files,
    live,
    busy,
    error,
    setError,
    report,
    refreshWorkspaces,
    open,
    send,
    stop,
    loadFile,
    panelRequest,
    setPanelRequest,
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
