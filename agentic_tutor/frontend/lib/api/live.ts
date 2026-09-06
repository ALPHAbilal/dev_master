import { EventSource } from "eventsource";
import type {
  Api,
  Identity,
  Handlers,
  StreamEvents,
  ScanEvents,
} from "./types";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export function createLiveApi(base: string, identity: Identity): Api {
  const url = (path: string) => {
    if (!base) throw new Error("Set NEXT_PUBLIC_API_BASE for live transport.");
    return base.replace(/\/$/, "") + path;
  };
  const headers = async () => {
    const token = await identity.getToken();
    if (!token || !identity.user_id)
      throw new Error("Sign in before connecting to the backend.");
    // user_id travels in a header, never as an extra JSON field (AsideBody forbids extras).
    return { Authorization: `Bearer ${token}`, "X-User-Id": identity.user_id };
  };
  async function request<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(url(path), {
      method: body === undefined ? "GET" : "POST",
      headers: { ...(await headers()), "Content-Type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) {
      const value = await response.text();
      throw new ApiError(response.status, value || response.statusText);
    }
    return response.json() as Promise<T>;
  }
  function subscribe<T extends StreamEvents | ScanEvents>(
    path: string,
    handlers: Handlers<T>,
  ): () => void {
    let source: EventSource | undefined,
      disposed = false;
    try {
      // Standards-compatible EventSource with a fetch hook: native EventSource has no
      // Authorization-header option. Refresh the token on every reconnect, no URL secrets.
      source = new EventSource(url(path), {
        fetch: async (input, init) =>
          fetch(input, {
            ...init,
            headers: {
              ...Object.fromEntries(new Headers(init?.headers)),
              ...(await headers()),
            },
          }),
      });
      for (const key of Object.keys(handlers).filter((k) => k !== "error"))
        source.addEventListener(key, (e) => {
          if (disposed) return;
          try {
            const callback = handlers[key as keyof T] as
              ((value: unknown) => void) | undefined;
            callback?.(JSON.parse((e as MessageEvent).data));
          } catch (error) {
            handlers.error?.(
              error instanceof Error ? error : new Error(String(error)),
            );
          }
        });
      source.onerror = () => {
        if (!disposed)
          handlers.error?.(new Error("Stream disconnected; reconnecting."));
      };
    } catch (error) {
      queueMicrotask(() => {
        if (!disposed)
          handlers.error?.(
            error instanceof Error ? error : new Error(String(error)),
          );
      });
    }
    return () => {
      disposed = true;
      source?.close();
    };
  }
  const id = (value: string | number) => encodeURIComponent(String(value));
  return {
    codebases: () => request("/codebases"),
    register: (body) => request("/codebases", body),
    open: (value) => request(`/codebases/${id(value)}/open`, {}),
    init: (body) => request("/session", body),
    map: () => request("/session/map", {}),
    resume: () => request("/session/resume", {}),
    park: (value, unit_id) =>
      request(`/journey/${id(value)}/park`, { unit_id }),
    snapshot: (value, since) =>
      request(`/journey/${id(value)}${since == null ? "" : `?since=${since}`}`),
    answer: (value, body) => request(`/journey/${id(value)}/answer`, body),
    aside: (value, body) => request(`/journey/${id(value)}/aside`, body),
    workspace: (body) => request("/workspace", body),
    stream: (value, handlers) =>
      subscribe<StreamEvents>(`/journey/${id(value)}/stream`, handlers),
    scan: (handlers) => subscribe<ScanEvents>("/session/map/stream", handlers),
  };
}
