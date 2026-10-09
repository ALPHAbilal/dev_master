"use client";
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { useRouter } from "next/navigation";
import { useTutor } from "@/lib/session";
import type { ScanEvents, Unit } from "@/lib/api/types";
import Sidebar from "./Sidebar";
import Icon from "./Icon";
import ErrorBanner from "./ErrorBanner";
import BatchPlanner from './BatchPlanner';
import StationDetails from './StationDetails';
import { useAuth } from '@/lib/auth';
import { defaultBatchSettings, stationHighlights } from '@/lib/scanner';
import scannerDemo from '@/lib/scanner-demo.json';
const dy = [0, 4, -3, 5, -2, 3, -4, 2],
  rot = [-3.5, 2.5, -1.5, 3, -2.5, 1.5, -3, 2],
  gw = [64, 82, 52, 74, 90, 58, 78, 66];
function vars(i: number): CSSProperties {
  return {
    "--dy": `${dy[i % 8]}px`,
    "--rot": `${rot[i % 8]}deg`,
    "--gw": `${gw[i % 8]}px`,
  } as CSSProperties;
}
function Pill({
  unit,
  index,
  state,
  open,
}: {
  unit: ScanEvents["unit"];
  index: number;
  state: string;
  open(): void;
}) {
  const target = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const real = target.current,
      log = document.getElementById("logBox"),
      scope = real?.closest(".scan-screen");
    if (
      !real ||
      !log ||
      !scope ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const to = real.getBoundingClientRect(),
      from = log.getBoundingClientRect();
    const flyer = real.cloneNode(true) as HTMLElement;
    flyer.className = "flyer";
    flyer.removeAttribute("role");
    flyer.removeAttribute("tabindex");
    flyer.style.left = `${from.right - 40}px`;
    flyer.style.top = `${from.top + from.height * 0.42}px`;
    scope.appendChild(flyer);
    real.style.visibility = "hidden";
    const frame = requestAnimationFrame(() => {
      flyer.style.transform = `translate(${to.left - (from.right - 40)}px,${to.top - (from.top + from.height * 0.42)}px)`;
    });
    const timer = setTimeout(() => {
      flyer.remove();
      real.style.visibility = "";
      real.classList.add("land");
    }, 460);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(timer);
      flyer.remove();
      real.style.visibility = "";
    };
  }, []);
  return (
    <div
      ref={target}
      className={"pill " + state}
      style={vars(index)}
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
      }}
    >
      <span className={"g " + state} />
      <span className="slug">{unit.slug}</span>
      {state === "now" && <span className="flag">current</span>}
    </div>
  );
}
export default function Scan() {
  const tutor = useTutor(),
    router = useRouter();
  const identity = useAuth();
  const [batchSettings, setBatchSettings] = useState(defaultBatchSettings);
  const [preview, setPreview] = useState(false);
  const [left, setLeft] = useState(true),
    [source, setSource] = useState(""),
    [imported, setImported] = useState(false),
    [importing, setImporting] = useState(false),
    [scanning, setScanning] = useState(false),
    [complete, setComplete] = useState(false),
    [thinking, setThinking] = useState(""),
    [logs, setLogs] = useState<string[]>([]),
    [units, setUnits] = useState<ScanEvents["unit"][]>([]),
    [limit, setLimit] = useState(3),
    [detail, setDetail] = useState<ScanEvents["unit"] | null>(null),
    [fade, setFade] = useState(false);
  const picker = useRef<HTMLInputElement>(null),
    stop = useRef<(() => void) | null>(null),
    active = useRef(true),
    mapping = useRef(false),
    importLock = useRef(false),
    bag = useRef<HTMLDivElement>(null);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      stop.current?.();
    };
  }, []);
  const name =
    source
      .trim()
      .replace(/[\\/]+$/, "")
      .split(/[\\/]/)
      .pop() || "codebase";
  async function browse(files: FileList | null) {
    if (!files?.length) return;
    const selected = Array.from(files),
      root = (selected[0].webkitRelativePath || selected[0].name).split("/")[0];
    setSource(root);
    const entries = await Promise.all(
      selected
        .filter(
          (f) =>
            f.size < 2_000_000 &&
            !/(^|\/)(node_modules|\.git)(\/|$)/.test(f.webkitRelativePath),
        )
        .map(
          async (f) =>
            [
              f.webkitRelativePath.split("/").slice(1).join("/") || f.name,
              await f.text(),
            ] as const,
        ),
    );
    tutor.setFiles(Object.fromEntries(entries));
  }
  async function importSource() {
    if (!source.trim() || importLock.current) return;
    importLock.current = true;
    setImporting(true);
    tutor.setError("");
    try {
      const value = source.trim();
      // An https:// value is a git repo to clone; anything else is a host path to register.
      const cb = /^https:\/\/\S+$/.test(value)
        ? await tutor.api.importRepo({
            name: name.replace(/\.git$/, ""),
            git_url: value,
          })
        : await tutor.api.register({ name, source: value });
      await tutor.api.open(cb.codebase_id);
      tutor.setCodebaseId(cb.codebase_id);
      await tutor.refreshCodebases();
      if (active.current) setImported(true);
    } catch (error) {
      tutor.report(error);
    } finally {
      importLock.current = false;
      if (active.current) setImporting(false);
    }
  }
  async function generate() {
    if (mapping.current) return;
    if (complete) return;
    if (tutor.isStub || preview) {
      setUnits(scannerDemo.slice(0, batchSettings.initial).map(station => ({ ...station, highlights: station.contract.highlights })));
      setLimit(batchSettings.initial);
      setComplete(true);
      setLogs(['Preview · sample stations from soufiane_prompts. No scan or background job was run.']);
      return;
    }
    mapping.current = true;
    setScanning(true);
    setLimit(batchSettings.initial);
    tutor.setError("");
    stop.current?.();
    stop.current = tutor.api.scan({
      thinking: (e) => {
        if (active.current) {
          setThinking(e.text);
          setLogs((old) => [...old, e.text]);
        }
      },
      unit: (e) => {
        if (active.current)
          setUnits((old) =>
            old.some((u) => u.slug === e.slug && u.file === e.file)
              ? old
              : [...old, e],
          );
      },
      done: () => {
        if (active.current) setThinking("");
      },
      error: () => {
        /* map response remains authoritative when the target SSE route is absent */
      },
    });
    try {
      const state = await tutor.api.map();
      if (!active.current) return;
      await tutor.adopt(state);
      const update = await tutor.api.snapshot(state.journey_id);
      if (!active.current) return;
      if (update.snapshot) { setUnits(update.snapshot.units); setLimit(update.snapshot.units.length); }
      setComplete(true);
    } catch (error) {
      tutor.report(error);
    } finally {
      mapping.current = false;
      stop.current?.();
      stop.current = null;
      if (active.current) {
        setScanning(false);
        setThinking("");
      }
    }
  }
  function reset() {
    if (mapping.current || importLock.current) return;
    setImported(false);
    setPreview(false);
    setComplete(false);
    setUnits([]);
    setLogs([]);
    setDetail(null);
  }
  const visible = units.slice(0, limit),
    pending = complete
      ? 0
      : Math.max(0, (scanning ? limit : batchSettings.initial) - visible.length);
  const stateOf = (u: ScanEvents["unit"]) => {
    const found = tutor.snapshot?.units.find(
      (v) => v.slug === u.slug && v.file === u.file,
    );
    return found?.state === "OWNED"
      ? "done"
      : found?.id === tutor.driver?.unit_id || found?.state === "ACTIVE"
        ? "now"
        : "pend";
  };
  const detailUnit = tutor.snapshot?.units.find(
      (u) => u.slug === detail?.slug && u.file === detail?.file,
    ),
    reachable = detailUnit && detailUnit.state !== "QUEUED";
  const axes =
    tutor.snapshot?.axes.filter((a) => a.unit_id === detailUnit?.id) || [];
  return (
    <main className="scan-screen">
      <div className="app">
        <Sidebar
          collapsed={!left}
          toggle={() => setLeft(!left)}
          add={reset}
          settings={() => router.push("/")}
        />
        <div className="canvas">
          <div className="stage">
            <div
              className={"import-view" + (imported ? " gone" : "")}
              id="importView"
              inert={imported}
            >
              <div className="import-card">
                <div className="import-eyebrow">Import codebase</div>
                <p className="scanner-intro">Start with 1–3 stations. Your learning profile and future batches stay with this codebase.</p>
                <div className="import-field">
                  <input
                    id="importInput"
                    spellCheck={false}
                    placeholder="Repo URL or local path"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void importSource();
                      }
                    }}
                  />
                  <button
                    className="browse"
                    id="browseBtn"
                    title="Choose a folder"
                    onClick={() => picker.current?.click()}
                  >
                    <Icon name="folder" />
                  </button>
                </div>
                {importing ? (
                  <div className="import-prog">
                    <span className="spin" />
                    <span>Connecting…</span>
                  </div>
                ) : (
                  <button
                    className="import-go"
                    id="importGo"
                    disabled={!source.trim()}
                    onClick={() => void importSource()}
                  >
                    Import
                  </button>
                )}
                <input
                  ref={picker}
                  type="file"
                  id="dirPicker"
                  {...{ webkitdirectory: "", directory: "" }}
                  multiple
                  hidden
                  onChange={(e) => {
                    void browse(e.target.files).catch(tutor.report);
                  }}
                />
                <button className="browse-example" onClick={() => { setSource('soufiane_prompts'); setPreview(true); setImported(true); }}>Preview example stations</button>
              </div>
            </div>
            <div id="scanView" className={imported ? "on" : ""} inert={!imported || !!detail}>
              <div className="title-row">
                <span className="fn" id="scanFn">
                  {name}
                </span>
                <span className="path" id="scanPath">
                  {source}
                </span>
              </div>
              <BatchPlanner key={`${identity.user_id}:${preview ? 'example' : tutor.codebaseId}`} user={identity.user_id} codebase={preview ? 'example:soufiane_prompts' : String(tutor.codebaseId ?? source)} name={name} onSettings={setBatchSettings} demo={tutor.isStub || preview} />
              {tutor.isStub || preview ? <p className="scanner-intro">Frontend preview · sample stations from soufiane_prompts</p> : <p className="scanner-intro">Batch preferences are saved locally. The current scan service controls how many stations it returns.</p>}
              <div className="boxes">
                <div className="box" id="logBox">
                  <div className="box-label">Agent log</div>
                  <div className="think">
                    <span
                      className={"t-think" + (!scanning ? " idle" : "")}
                      id="thinkRoot"
                    >
                      <span className="t-think-sizer">
                        Tracing dependencies…
                      </span>
                      <span
                        className="t-think-text"
                        id="thinkText"
                        data-text={thinking}
                      >
                        {thinking}
                      </span>
                    </span>
                  </div>
                  <div className="log-list" id="logList">
                    {logs.map((text, i) => (
                      <div
                        className={
                          "chip" +
                          (i < logs.length - 1 || complete ? " spent" : "")
                        }
                        key={i}
                      >
                        <span className="ic">⌁</span>
                        {text}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="box bag-box">
                  <div className="box-label">Learning stations</div>
                  <div
                    className={
                      "bag-caps" +
                      (!visible.length && !pending ? " hidden" : "")
                    }
                    id="capTop"
                  >
                    <span>first</span>
                  </div>
                  <div className="bag-scroll" id="bagScroll">
                    <div
                      className="bag"
                      id="bag"
                      ref={bag}
                      onScroll={(e) =>
                        setFade(
                          e.currentTarget.scrollTop <
                            e.currentTarget.scrollHeight -
                              e.currentTarget.clientHeight -
                              4,
                        )
                      }
                    >
                      {visible.map((u, i) => (
                        <Pill
                          key={u.file + u.slug}
                          unit={u}
                          index={i}
                          state={stateOf(u)}
                          open={() => setDetail(u)}
                        />
                      ))}
                      {Array.from(
                        { length: Math.min(pending, 200) },
                        (_, i) => (
                          <div
                            key={"ghost-" + i}
                            className="pill ghost"
                            style={vars(visible.length + i)}
                          >
                            <span className="ghost-dot" />
                            <span className="ghost-bar" />
                          </div>
                        ),
                      )}
                    </div>
                    <div
                      className={"bag-fade" + (fade ? " on" : "")}
                      id="bagFade"
                    />
                  </div>
                  <div
                    className={
                      "bag-caps" +
                      (!visible.length && !pending ? " hidden" : "")
                    }
                    id="capBot"
                  >
                    <span className="last">latest generated</span>
                  </div>
                </div>
              </div>
              <div className="gen-row" id="genRow">
                {scanning ? (
                  <span className="gen-busy">
                    <span className="mini" />
                    generating {limit}…
                  </span>
                ) : complete && limit >= units.length ? (
                  <span className="gen-complete">
                    <Icon name="arrow" />
                    {units.length} {units.length === 1 ? 'station' : 'stations'} ready · your path continues in batches
                  </span>
                ) : (
                  <div className="req">
                    <span className="req-unit">{batchSettings.initial} initial stations</span>
                    <button className="req-go" onClick={() => void generate()}>
                      <Icon name="arrow" />
                      {tutor.isStub || preview ? 'Preview stations' : 'Generate'}
                    </button>
                  </div>
                )}
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
                <button
                  className={"open-lesson" + (!reachable ? " locked" : "")}
                  id="openLesson"
                  disabled={!reachable || scanning}
                  onClick={() => router.push("/")}
                >
                  <Icon name="arrow" />
                  {reachable ? "Open lesson" : "Locked"}
                </button>
              </div>
              <div className="detail-body" id="detailBody">
                {detail && (
                  <>
                    <div className="detail-slug">{detail.slug}</div>
                    <div className="detail-sub">
                      {detail.file} · L{detail.lo}–{detail.hi}
                    </div>
                    {(detail.contract || detailUnit?.contract) && <StationDetails key={detail.slug} contract={{ ...(detail.contract || detailUnit?.contract)!, highlights: stationHighlights(detailUnit || detail) }} files={tutor.files} />}
                    {!detail.contract && !detailUnit?.contract && <>
                    <div className="meta-grid">
                      <span className="k">State</span>
                      <span className="v">{detailUnit?.state || "LOCKED"}</span>
                      <span className="k">Position</span>
                      <span className="v">
                        #{(detailUnit?.ordinal ?? 0) + 1} in dependency order
                      </span>
                      <span className="k">Depth</span>
                      <span className="v">
                        {detailUnit?.depth ?? 0} ·{" "}
                        {detailUnit?.parent_id ? "nested" : "top-level"}
                      </span>
                    </div>
                    <div className="sec-l">
                      Assessment axes · {axes.length}
                    </div>
                    <div className="axes">
                      {axes.map((a) => (
                        <span className="axis" key={a.axis}>
                          {a.axis}
                        </span>
                      ))}
                    </div>
                    {tutor.files[detail.file] && (
                      <>
                        <div className="sec-l">
                          Source · L{detail.lo}–{detail.hi}
                        </div>
                        <div className="code">
                          {tutor.files[detail.file]
                            .split("\n")
                            .slice(detail.lo - 1, detail.hi)
                            .map((line, i) => (
                              <div className="cl" key={i}>
                                <span className="ln">{detail.lo + i}</span>
                                <span className="src">{line || " "}</span>
                              </div>
                            ))}
                        </div>
                      </>
                    )}
                    <p className="scanner-intro">This station has a source anchor. Its learning contract has not been provided yet.</p>
                    </>}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      <ErrorBanner />
    </main>
  );
}
