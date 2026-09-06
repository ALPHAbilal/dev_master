"use client";
import { Fragment, useEffect, useRef, useState } from "react";
import { useTutor } from "@/lib/session";
import type { Id, Message, Ref } from "@/lib/api/types";
import Icon from "./Icon";
import { RefChip, RefList } from "./Refs";
import { payload } from "./Map";
function autosize(el: HTMLTextAreaElement) {
  el.style.height = "auto";
  el.style.height = el.scrollHeight + "px";
}
function Text({ content }: { content: string }) {
  return (
    <>
      {content
        .split(/(`[^`\n]+`)/g)
        .map((part, i) =>
          part.startsWith("`") && part.endsWith("`") ? (
            <code key={i}>{part.slice(1, -1)}</code>
          ) : (
            part
          ),
        )}
    </>
  );
}
function Code({ code, lang }: { code: string; lang: string }) {
  const [closed, setClosed] = useState(false);
  return (
    <div className="tblk">
      <div className="tblk-eyebrow">
        <span className="gl">◆</span>Tutor · generated
      </div>
      <div className={"ai-code" + (closed ? " collapsed" : "")}>
        <button
          className="code-head"
          aria-expanded={!closed}
          onClick={() => setClosed(!closed)}
        >
          <span className="ch-title">snippet</span>
          <span className="ch-meta">
            {lang.toUpperCase()} · {code.split("\n").length} LN
          </span>
          <span className="ch-caret">{closed ? "+" : "−"}</span>
        </button>
        <div className="code-body">
          <div className="code-inner">
            {code.split("\n").map((line, i) => (
              <div className="cl" key={i}>
                <span className="ln">{i + 1}</span>
                <span className="src">
                  {(line || " ")
                    .split(
                      /("[^"\n]*"|'[^'\n]*'|#.*$|\b(?:def|return|for|if|not|in|and|or|else|None|True|False)\b)/g,
                    )
                    .map((token, index) => (
                      <span
                        key={index}
                        className={
                          token.startsWith("#")
                            ? "c"
                            : /^["']/.test(token)
                              ? "s"
                              : /^(def|return|for|if|not|in|and|or|else|None|True|False)$/.test(
                                    token,
                                  )
                                ? "k"
                                : undefined
                        }
                      >
                        {token}
                      </span>
                    ))}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
function MessageBody({ message }: { message: Message }) {
  const pieces = message.content.split(/(```[^\n]*\n[\s\S]*?```)/g);
  return (
    <>
      {pieces.map((part, i) =>
        part.startsWith("```") ? (
          <Code
            key={i}
            lang={part.slice(3, part.indexOf("\n")) || "py"}
            code={part.slice(part.indexOf("\n") + 1, -3).replace(/\n$/, "")}
          />
        ) : (
          <div className="say" key={i}>
            <Text content={part} />
          </div>
        ),
      )}
      <RefList refs={message.refs || []} />
    </>
  );
}
function AsideThread({ id, expanded }: { id: string; expanded: boolean }) {
  const tutor = useTutor(),
    thread = tutor.snapshot?.aside_threads.find((t) => t.id === id);
  const [closed, setClosed] = useState(!expanded),
    [question, setQuestion] = useState("");
  const request = useRef<string | null>(null);
  useEffect(() => {
    if (expanded) {
      setClosed(false);
      const timer = setTimeout(
        () =>
          document
            .getElementById(`aside-${id}`)
            ?.scrollIntoView({ block: "center" }),
        0,
      );
      return () => clearTimeout(timer);
    }
  }, [expanded, id]);
  async function send() {
    if (!question.trim() || tutor.busy) return;
    request.current ||= crypto.randomUUID();
    const ack = await tutor.aside(question.trim(), [], request.current, id);
    if (ack) {
      request.current = null;
      setQuestion("");
    }
  }
  return (
    <div
      className={"aside" + (closed ? " collapsed" : "")}
      id={`aside-${id}`}
      data-id={id}
    >
      <div className="aside-eyebrow">aside</div>
      <div className="aside-cell">
        <button
          className="aside-head"
          aria-expanded={!closed}
          onClick={() => setClosed(!closed)}
        >
          <span className="ah-title">{thread?.title || "Side question"}</span>
          <span className="ah-caret">{closed ? "+" : "−"}</span>
        </button>
        <div className="aside-body" inert={closed}>
          <div className="aside-inner">
            <div className="aside-pad">
              {tutor.snapshot?.conversation
                .filter((m) => m.thread_id === id)
                .map((m) => (
                  <div
                    className={"aside-qa " + m.role}
                    key={m.id}
                    data-message-id={m.id}
                  >
                    <MessageBody message={m} />
                  </div>
                ))}
              {Object.values(tutor.tokens)
                .filter((t) => t.thread_id === id)
                .map((t) => (
                  <div className="aside-qa tutor" key={t.turn_id}>
                    <span className="say">{t.text}</span>
                  </div>
                ))}
              <div className="aside-ask">
                <textarea
                  rows={1}
                  placeholder="Ask a follow-up…"
                  value={question}
                  onChange={(e) => {
                    setQuestion(e.target.value);
                    request.current = null;
                    autosize(e.target);
                  }}
                  onKeyDown={(e) => {
                    if (
                      e.key === "Enter" &&
                      !e.shiftKey &&
                      !e.nativeEvent.isComposing
                    ) {
                      e.preventDefault();
                      void send();
                    }
                  }}
                />
                <button
                  className="send"
                  title="Ask"
                  disabled={tutor.busy || !question.trim()}
                  onClick={() => void send()}
                >
                  <Icon name="arrow" size={13} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
export default function Conversation({
  refs,
  setRefs,
  expanded,
  openAside,
  attach,
}: {
  refs: Ref[];
  setRefs(refs: Ref[]): void;
  expanded: string | null;
  openAside(id: string): void;
  attach(ref: Ref, x: number, y: number): void;
}) {
  const tutor = useTutor(),
    [mode, setMode] = useState<"answer" | "aside">("answer"),
    [text, setText] = useState("");
  const request = useRef<string | null>(null),
    input = useRef<HTMLTextAreaElement>(null),
    end = useRef<HTMLDivElement>(null),
    previousCount = useRef(0);
  const count = tutor.snapshot?.conversation.length || 0;
  useEffect(() => {
    if (previousCount.current && count > previousCount.current)
      end.current?.scrollIntoView({ block: "end", behavior: "smooth" });
    previousCount.current = count;
  }, [count]);
  useEffect(() => {
    if (refs.length) input.current?.focus();
  }, [refs.length]);
  async function send() {
    if ((!text.trim() && !refs.length) || tutor.busy) return;
    let success: unknown;
    if (mode === "aside") {
      request.current ||= crypto.randomUUID();
      const origin = refs.find((r) => r.kind === "convo");
      const ack = await tutor.aside(
        text.trim(),
        refs,
        request.current,
        undefined,
        origin?.kind === "convo" ? origin.source.message_id : undefined,
      );
      if (ack) {
        openAside(ack.thread_id);
        success = ack;
      }
    } else success = await tutor.answer(text.trim(), refs);
    if (success) {
      setText("");
      setRefs([]);
      request.current = null;
      if (input.current) {
        input.current.value = "";
        autosize(input.current);
      }
    }
  }
  function selection(event: React.MouseEvent) {
    const selection = window.getSelection(),
      snippet = selection?.toString();
    if (!selection || !snippet?.trim()) return;
    const element =
      selection.anchorNode?.parentElement?.closest<HTMLElement>(
        "[data-message-id]",
      );
    const focus =
      selection.focusNode?.parentElement?.closest<HTMLElement>(
        "[data-message-id]",
      );
    if (!element || focus !== element) return;
    const message = tutor.snapshot?.conversation.find(
      (m) => String(m.id) === element.dataset.messageId,
    );
    if (!message || !message.content.includes(snippet)) return;
    attach(
      {
        kind: "convo",
        label: "conversation",
        snippet,
        source: { message_id: message.id },
      },
      event.clientX,
      event.clientY,
    );
  }
  const seen = new Set<string>();
  return (
    <>
      <div className="convo-scroll">
        <div className="convo-inner" id="convo" onMouseUp={selection}>
          {tutor.snapshot?.conversation
            .slice()
            .sort((a, b) => a.sequence - b.sequence)
            .map((message) => {
              if (message.thread_kind === "aside" && message.thread_id) {
                if (seen.has(message.thread_id)) return null;
                seen.add(message.thread_id);
                return (
                  <AsideThread
                    key={"aside-" + message.thread_id}
                    id={message.thread_id}
                    expanded={expanded === message.thread_id}
                  />
                );
              }
              const grades =
                message.role === "learner"
                  ? tutor.snapshot?.lifecycle.filter(
                      (event) =>
                        event.event_type === "answer_evaluated" &&
                        payload(event).turn_id === message.turn_id,
                    ) || []
                  : [];
              return (
                <Fragment key={message.id}>
                  <div
                    className={"turn " + message.role}
                    data-message-id={message.id}
                  >
                    <MessageBody message={message} />
                  </div>
                  {grades.map((event) => {
                    const data = payload(event);
                    return (
                      <div className="feedback" key={event.id}>
                        <div className="fb-top">
                          <span className={"verdict " + String(data.verdict)}>
                            {String(data.verdict)}
                          </span>
                          <span className="cat">
                            {String(data.category || "")}
                          </span>
                          <span className="agent">JUDGE</span>
                        </div>
                        <div className="fb-body">
                          {String(
                            data.text ||
                              tutor.snapshot?.axis_wording[event.axis || ""] ||
                              "",
                          )}
                        </div>
                      </div>
                    );
                  })}
                </Fragment>
              );
            })}
          {tutor.snapshot?.aside_threads
            .filter((t) => !seen.has(t.id))
            .map((t) => (
              <AsideThread key={t.id} id={t.id} expanded={expanded === t.id} />
            ))}
          {[...(tutor.snapshot?.tool_calls || []), ...tutor.tools]
            .filter((t) =>
              ["read_code_slice", "read_workspace"].includes(t.capability),
            )
            .map((t, i) => (
              <div className="agent-run" key={`${t.turn_id}-${i}`}>
                <div className="ar-head">
                  {t.agent}
                  <span className="dot">·</span>
                  {t.step}
                </div>
                <div className="tool">
                  <span className="tname">{t.capability}</span>
                </div>
              </div>
            ))}
          {Object.values(tutor.tokens)
            .filter((t) => !t.thread_id || !seen.has(t.thread_id))
            .map((t) => (
              <div
                className={t.thread_id ? "aside-qa tutor" : "turn tutor"}
                key={t.turn_id + t.thread_id}
              >
                <div className="say">{t.text}</div>
              </div>
            ))}
          <div ref={end} />
        </div>
      </div>
      <div className="chatbar-wrap">
        <div className="composer" id="composer" data-mode={mode}>
          <div className="ref-tray" id="refTray">
            {refs.map((ref, i) => (
              <RefChip
                key={i}
                value={ref}
                remove={() => setRefs(refs.filter((_, index) => i !== index))}
              />
            ))}
          </div>
          <textarea
            ref={input}
            className="chat-input"
            rows={1}
            placeholder={mode === "answer" ? "Answer…" : "Side question…"}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              request.current = null;
              autosize(e.target);
            }}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <div className="composer-bar">
            <div
              className="mode-switch"
              id="modeSwitch"
              role="tablist"
              aria-label="Message mode"
            >
              {(["answer", "aside"] as const).map((value) => (
                <button
                  key={value}
                  className={"ms-opt" + (mode === value ? " on" : "")}
                  role="tab"
                  aria-selected={mode === value}
                  onClick={() => {
                    setMode(value);
                    input.current?.focus();
                  }}
                >
                  {value === "answer" ? "Answer" : "Side question"}
                </button>
              ))}
            </div>
            <button
              className="chat-send"
              id="chatSend"
              title="Send"
              disabled={
                tutor.busy || (!text.trim() && !refs.length) || !tutor.driver
              }
              onClick={() => void send()}
            >
              <Icon name="send" size={16} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
