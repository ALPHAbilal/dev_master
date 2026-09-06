"use client";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Ref } from "@/lib/api/types";
import Icon from "./Icon";
export function RefChip({ value, remove }: { value: Ref; remove?(): void }) {
  const [open, setOpen] = useState(false),
    [position, setPosition] = useState({ left: 8, top: 8 });
  const anchor = useRef<HTMLSpanElement>(null),
    pop = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (!open || !anchor.current || !pop.current) return;
    const r = anchor.current.getBoundingClientRect(),
      p = pop.current.getBoundingClientRect();
    setPosition({
      left: Math.max(
        8,
        Math.min(
          r.left + r.width / 2 - p.width / 2,
          window.innerWidth - p.width - 8,
        ),
      ),
      top: r.top - p.height - 8 < 8 ? r.bottom + 8 : r.top - p.height - 8,
    });
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const close = (event: Event) => {
      if (event.type === "keydown" && (event as KeyboardEvent).key !== "Escape")
        return;
      if (
        event.type === "click" &&
        (anchor.current?.contains(event.target as Node) ||
          pop.current?.contains(event.target as Node))
      )
        return;
      setOpen(false);
    };
    document.addEventListener("click", close);
    document.addEventListener("keydown", close);
    document.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", close);
      document.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);
  return (
    <>
      <span
        ref={anchor}
        className={"ref-chip" + (open ? " open" : "")}
        data-kind={value.kind}
        role="button"
        tabIndex={0}
        onClick={() => setOpen(!open)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen(!open);
          }
        }}
      >
        <span className="rc-ic">
          <Icon name={value.kind} />
        </span>
        <span className="rc-lb">{value.label}</span>
        {remove && (
          <button
            className="rc-x"
            title="Remove"
            onClick={(e) => {
              e.stopPropagation();
              remove();
            }}
          >
            <Icon name="close" />
          </button>
        )}
      </span>
      {open && (
        <div className="ref-pop" ref={pop} style={position}>
          <div className="rp-src">
            <Icon name={value.kind} />
            <span>{value.label}</span>
          </div>
          <pre>{value.snippet}</pre>
        </div>
      )}
    </>
  );
}
export function RefList({ refs }: { refs: Ref[] }) {
  return refs.length ? (
    <div className="msg-refs">
      {refs.map((ref, i) => (
        <RefChip key={i} value={ref} />
      ))}
    </div>
  ) : null;
}
