import { EventSource } from "eventsource";
import type {
  Api,
  Identity,
  Handlers,
  StreamEvents,
  PreparingEvents,
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
    // user_id travels in a header, never as an extra JSON field.
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
  function subscribe<T extends StreamEvents | PreparingEvents>(
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
              | ((value: unknown) => void)
              | undefined;
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
  const id = (value: string) => encodeURIComponent(value);
  const workspace = (value: string) => `/workspaces/${id(value)}`;
  return {
    workspaces: () => request("/workspaces"),
    importRepository: (body) => request("/workspaces/import", body),
    preparing: (value, handlers) =>
      subscribe<PreparingEvents>(`${workspace(value)}/preparing`, handlers),
    task: (value, task) => request(`${workspace(value)}/tasks/${id(task)}`),
    start: (value) => request(`${workspace(value)}/start`, {}),
    snapshot: (value, since) =>
      request(`${workspace(value)}${since == null ? "" : `?since=${since}`}`),
    send: (value, body) => request(`${workspace(value)}/messages`, body),
    stream: (value, handlers) =>
      subscribe<StreamEvents>(`${workspace(value)}/stream`, handlers),
    stop: (value) => request(`${workspace(value)}/stop`, {}),
    files: (value) => request(`${workspace(value)}/files`),
    file: (value, path) =>
      request(`${workspace(value)}/file?path=${encodeURIComponent(path)}`),
  };
}
