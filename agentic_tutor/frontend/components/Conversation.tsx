"use client";
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTutor } from "@/lib/session";
import type { Attachment, Id, Message } from "@/lib/api/types";
import Icon from "./Icon";
import { RefChip, RefList } from "./Refs";
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
                      /("[^"\n]*"|'[^'\n]*'|#.*$|\b(?:def|return|for|if|not|in|and|or|else|None|True|False|pass)\b)/g,
                    )
                    .map((token, index) => (
                      <span
                        key={index}
                        className={
                          token.startsWith("#")
                            ? "c"
                            : /^["']/.test(token)
                              ? "s"
                              : /^(def|return|for|if|not|in|and|or|else|None|True|False|pass)$/.test(
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
  const pieces = message.text.split(/(```[^\n]*\n[\s\S]*?```)/g);
  return (
    <>
      {pieces.map((part, i) =>
        part.startsWith("```") ? (
          <Code
            key={i}
            lang={part.slice(3, part.indexOf("\n")) || "py"}
            code={part.slice(part.indexOf("\n") + 1, -3).replace(/\n$/, "")}
          />
        ) : part.trim() ? (
          <div className="say" key={i}>
            <Text content={part.trim()} />
          </div>
        ) : null,
      )}
      <RefList refs={message.attachments || []} />
    </>
  );
}
// A turn to show: set when the learner clicks a story line or a ticked box.
export interface Target {
  task_id: Id;
  turn: number;
  at: number;
}
export default function Conversation({
  visible,
  target,
  attachments,
  setAttachments,
  attach,
}: {
  visible: boolean;
  target: Target | null;
  attachments: Attachment[];
  setAttachments(attachments: Attachment[]): void;
  attach(attachment: Attachment, x: number, y: number): void;
}) {
  const tutor = useTutor(),
    snapshot = tutor.snapshot,
    [text, setText] = useState("");
  const request = useRef<string | null>(null),
    input = useRef<HTMLTextAreaElement>(null),
    end = useRef<HTMLDivElement>(null),
    previousCount = useRef(0);
  const messages = snapshot?.conversation || [];
  const pending = Object.values(tutor.live).filter(
    (l) =>
      !messages.some(
        (m) => m.role === "tutor" && m.task_id === l.task_id && m.turn === l.turn,
      ),
  );
  const count = messages.length + pending.reduce((n, l) => n + l.text.length, 0);
  useEffect(() => {
    if (previousCount.current && count > previousCount.current)
      end.current?.scrollIntoView({ block: "end", behavior: "smooth" });
    previousCount.current = count;
  }, [count]);
  // On show: the clicked turn, flashed; otherwise the latest message.
  const shown = messages.length > 0;
  useLayoutEffect(() => {
    if (!visible || !shown) return;
    const turn =
      target &&
      document.querySelector<HTMLElement>(
        `#convo [data-task="${CSS.escape(target.task_id)}"][data-turn="${target.turn}"]`,
      );
    if (!turn) {
      end.current?.scrollIntoView({ block: "end" });
      return;
    }
    turn.scrollIntoView({ block: "center" });
    document
      .querySelectorAll("#convo .turn.target")
      .forEach((t) => t !== turn && t.classList.remove("target"));
    turn.classList.add("target");
  }, [visible, target, shown]);
  useEffect(() => {
    if (attachments.length) input.current?.focus();
  }, [attachments.length]);
  async function send() {
    if ((!text.trim() && !attachments.length) || tutor.busy || answering) return;
    request.current ||= crypto.randomUUID();
    // The box empties at once; if the message can't be sent, it comes back.
    const sent = { text, attachments, id: request.current };
    setText("");
    setAttachments([]);
    if (input.current) {
      input.current.value = "";
      autosize(input.current);
    }
    if (await tutor.send(sent.text.trim(), sent.attachments, sent.id))
      request.current = null;
    else {
      setText(sent.text);
      setAttachments(sent.attachments);
    }
  }
  function selection(event: React.MouseEvent) {
    const selected = window.getSelection(),
      snippet = selected?.toString();
    if (!selected || !snippet?.trim()) return;
    const element =
      selected.anchorNode?.parentElement?.closest<HTMLElement>(
        "[data-message-id]",
      );
    const focus =
      selected.focusNode?.parentElement?.closest<HTMLElement>(
        "[data-message-id]",
      );
    if (!element || focus !== element) return;
    const message = messages.find(
      (m) => String(m.id) === element.dataset.messageId,
    );
    if (!message || !message.text.includes(snippet)) return;
    attach(
      {
        kind: "conversation",
        label: "conversation",
        text: snippet,
        source: { message_id: message.id },
      },
      event.clientX,
      event.clientY,
    );
  }
  const title = (task_id: string) => {
    const task = snapshot?.ladder.find((t) => t.id === task_id);
    return task ? task.title : "";
  };
  const answering = snapshot?.where?.tutor === "answering";
  return (
    <>
      <div className="convo-scroll">
        <div className="convo-inner" id="convo" onMouseUp={selection}>
          {messages.map((message, i) => {
            const ticks =
              message.role === "learner"
                ? snapshot?.story.filter(
                    (l) =>
                      l.kind === "ticked" &&
                      l.task_id === message.task_id &&
                      l.turn === message.turn,
                  ) || []
                : [];
            return (
              <Fragment key={message.id}>
                {messages[i - 1]?.task_id !== message.task_id && (
                  <div className="task-divider">
                    <span>{title(message.task_id)}</span>
                  </div>
                )}
                <div
                  className={"turn " + message.role}
                  data-message-id={message.id}
                  data-task={message.task_id}
                  data-turn={message.turn}
                >
                  <MessageBody message={message} />
                </div>
                {ticks.map((l) => (
                  <div className="tick-note" key={l.id}>
                    ☑ {l.text}
                  </div>
                ))}
              </Fragment>
            );
          })}
          {pending.map((l) => (
            <Fragment key={`${l.task_id}:${l.turn}`}>
              {l.tools.length > 0 && (
                <div className="agent-run">
                  {l.tools.map((doing, i) => (
                    <div className="tool" key={i}>
                      <span className="tname">{doing}</span>
                    </div>
                  ))}
                </div>
              )}
              {l.text && (
                <div className="turn tutor">
                  <div className="say">{l.text}</div>
                </div>
              )}
            </Fragment>
          ))}
          <div ref={end} />
        </div>
      </div>
      <div className="chatbar-wrap">
        <div className="composer" id="composer">
          {attachments.length > 0 && (
            <div className="ref-tray" id="refTray">
              {attachments.map((attachment, i) => (
                <RefChip
                  key={i}
                  value={attachment}
                  remove={() =>
                    setAttachments(attachments.filter((_, index) => i !== index))
                  }
                />
              ))}
            </div>
          )}
          <div className="composer-row">
            <textarea
              ref={input}
              className="chat-input"
              rows={1}
              placeholder="Answer…"
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
            {answering || tutor.busy ? (
              <button
                className="chat-send stop"
                id="chatSend"
                aria-label="Stop"
                onClick={() => void tutor.stop()}
              >
                <span className="sq" />
              </button>
            ) : (
              <button
                className="chat-send"
                id="chatSend"
                aria-label="Send"
                disabled={(!text.trim() && !attachments.length) || !snapshot?.where}
                onClick={() => void send()}
              >
                <Icon name="send" size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
