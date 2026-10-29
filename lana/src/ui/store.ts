import { useCallback, useEffect, useRef, useState } from 'react';
import { CONVERSATION_KEY as KEY, type Conversation } from './conversation';

// The conversation in Chrome's session storage, as a React hook. Both views use it; each write
// carries the writer's id so a view never re-applies its own older write over a newer one.

const me = crypto.randomUUID();

interface Stored {
  conversation: Conversation;
  writer: string;
}

export function useConversation() {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loaded, setLoaded] = useState(false);
  const latest = useRef<Conversation | null>(null);

  useEffect(() => {
    void browser.storage.session.get(KEY).then((s) => {
      latest.current = (s[KEY] as Stored | undefined)?.conversation ?? null;
      setConversation(latest.current);
      setLoaded(true);
    });
    const listener = (changes: Record<string, { newValue?: unknown }>, area: string) => {
      if (area !== 'session' || !(KEY in changes)) return;
      const next = changes[KEY]!.newValue as Stored | undefined;
      if (next?.writer === me) return;
      latest.current = next?.conversation ?? null;
      setConversation(latest.current);
    };
    browser.storage.onChanged.addListener(listener);
    return () => browser.storage.onChanged.removeListener(listener);
  }, []);

  /** Applies a change on top of the newest state, shows it, and saves it. */
  const update = useCallback((change: (c: Conversation) => Conversation) => {
    if (!latest.current) return Promise.resolve();
    latest.current = change(latest.current);
    setConversation(latest.current);
    return browser.storage.session.set({ [KEY]: { conversation: latest.current, writer: me } satisfies Stored });
  }, []);

  /** Starts a new conversation, replacing any other. */
  const start = useCallback((conversation: Conversation) => {
    latest.current = conversation;
    setConversation(conversation);
    return browser.storage.session.set({ [KEY]: { conversation, writer: me } satisfies Stored });
  }, []);

  return { conversation, loaded, update, start };
}
