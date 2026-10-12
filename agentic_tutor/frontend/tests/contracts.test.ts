import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { createLiveApi } from "../lib/api/live";
import { createStubApi } from "../lib/api/stub";
import { editKey } from "../lib/editor";
import type { Api, Snapshot } from "../lib/api/types";

async function snapshot(api: Api): Promise<Snapshot> {
  const update = await api.snapshot("demo");
  assert.ok(update.snapshot);
  return update.snapshot;
}
const say = (api: Api, id: string, text = "…") =>
  api.send("demo", { client_message_id: id, text, attachments: [] });

test("demo mode opens task T3 inside issue I2, with its sheet and nested issues", async () => {
  const s = await snapshot(createStubApi({ delay: 0 }));
  assert.deepEqual(
    s.ladder.map((t) => t.status),
    ["done", "done", "current", "later", "later", "later"],
  );
  const t3 = s.ladder[2];
  assert.equal(t3.sheet.the_job_is_done.text, "the fix works: a guest gets a real answer");
  const [c17, c15] = t3.sheet.concepts;
  assert.equal(c17.checked, true);
  assert.equal(c17.boxes[0].ticked_at_turn, 3);
  assert.equal(c17.boxes[0].text, "finds the real error behind the generic message");
  // A concept's box hides its text until it is ticked.
  assert.equal(c15.checked, false);
  assert.equal(c15.boxes[0].text, null);
  assert.deepEqual(
    t3.issues.map((i) => [i.id, i.parent_issue_id, i.status]),
    [["I1", null, "open"], ["I2", "I1", "open"]],
  );
  assert.deepEqual(
    [s.where?.task_id, s.where?.issue_id, s.where?.depth],
    ["T3", "I2", 2],
  );
  assert.equal(s.workspace.tasks_done, 2);
});

test("a turn streams the reply, then code clears issue I2 and goes back one step", async () => {
  const api = createStubApi({ delay: 0 });
  const text: string[] = [];
  const stop = api.stream("demo", { tutor: (e) => text.push(e.text) });
  const first = await say(api, "message-1", "Lines 469–470 return [] for a guest.");
  stop();
  assert.equal(first.turn, 6);
  assert.match(text.join(""), /for a guest the loop gets \[\]/);
  // The same client_message_id is one message, not two.
  assert.deepEqual(await say(api, "message-1"), first);
  const s = await snapshot(api);
  assert.equal(
    s.conversation.filter((m) => m.task_id === "T3" && m.turn === 6).length,
    2,
  );
  assert.equal(s.ladder[2].issues.find((i) => i.id === "I2")?.status, "cleared");
  const back = s.story.at(-1)!;
  assert.equal(back.kind, "came_back");
  assert.equal(back.picking_up, "you get last([]) now; connect it to label");
  assert.deepEqual([s.where?.issue_id, s.where?.tutor], ["I1", "waiting_for_you"]);
});

test("stop ends the reply where it is and keeps what was said", async () => {
  const api = createStubApi({ delay: 4 });
  let words = 0;
  api.stream("demo", { tutor: () => words++ });
  const reply = say(api, "message-stop");
  while (words < 3) await new Promise((r) => setTimeout(r, 2));
  await api.stop("demo");
  const { turn } = await reply;
  const s = await snapshot(api);
  const tutor = s.conversation.find((m) => m.role === "tutor" && m.task_id === "T3" && m.turn === turn)!;
  assert.ok(tutor.text.length > 0);
  assert.ok(tutor.text.length < "Right: for a guest the loop gets []. Now connect it: after a loop over [], what is label?".length);
  assert.equal(s.where?.tutor, "waiting_for_you");
});

test("the last box closes task T3 and opens task T4 with a fresh sheet", async () => {
  const api = createStubApi({ delay: 0 });
  for (let i = 0; i < 5; i++) await say(api, `message-${i}`);
  const s = await snapshot(api);
  const [t3, t4] = [s.ladder[2], s.ladder[3]];
  assert.equal(t3.status, "done");
  assert.ok(t3.sheet.concepts.every((c) => c.checked));
  assert.equal(t3.issues.find((i) => i.id === "I3")?.status, "saved");
  assert.equal(t4.status, "current");
  assert.ok(t4.sheet.concepts.every((c) => !c.checked && c.boxes[0].text === null));
  assert.deepEqual(
    s.story.filter((l) => l.task_id === "T3").at(-1)?.kind,
    "done",
  );
  assert.equal(s.where?.task_id, "T4");
  assert.equal(s.workspace.tasks_done, 3);
  const unchanged = await api.snapshot("demo", s.revision);
  assert.equal(unchanged.snapshot, null);
});

test("importing a repository runs the four preparing steps, then start opens task T1", async () => {
  const api = createStubApi({ delay: 0 });
  await assert.rejects(
    api.importRepository({ name: "x", git_url: "http://example.com/x" }),
    /https/,
  );
  const { workspace_id } = await api.importRepository({
    name: "your-repository",
    git_url: "https://github.com/you/your-repository",
  });
  const done: string[] = [],
    tasks: string[] = [];
  await new Promise<void>((resolve) => {
    api.preparing(workspace_id, {
      step: (e) => e.state === "done" && done.push(e.name),
      task: (e) => tasks.push(e.id),
      ready: () => resolve(),
    });
  });
  assert.deepEqual(done, ["copying", "concepts", "tasks", "ordering"]);
  assert.equal(tasks.length, 6);
  await api.start(workspace_id);
  const s = (await api.snapshot(workspace_id)).snapshot!;
  assert.equal(s.workspace.preparing, "ready");
  assert.equal(s.ladder[0].status, "current");
  assert.equal(s.conversation[0].role, "tutor");
});

test("editor indentation preserves content and selection", () => {
  assert.deepEqual(editKey("if x:", 5, 5, "Enter", false), {
    value: "if x:\n    ",
    start: 10,
    end: 10,
  });
  assert.deepEqual(editKey("a\nb\n", 0, 4, "Tab", false), {
    value: "    a\n    b\n",
    start: 4,
    end: 12,
  });
  assert.deepEqual(editKey("    a\n    b", 0, 11, "Tab", true), {
    value: "a\nb",
    start: 0,
    end: 3,
  });
});

test("live calls use Bearer headers, exact bodies and the new routes", async () => {
  const observed: {
    url: string;
    auth: string | undefined;
    user: string | string[] | undefined;
    body: unknown;
  }[] = [];
  const server = createServer(async (req, res) => {
    let data = "";
    for await (const part of req) data += part;
    observed.push({
      url: req.url!,
      auth: req.headers.authorization,
      user: req.headers["x-user-id"],
      body: data ? JSON.parse(data) : null,
    });
    if (req.url?.endsWith("/stream")) {
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      res.write(
        'event: tutor\ndata: {"task_id":"T3","turn":6,"text":"hello"}\n\nevent: revision\ndata: {"revision":4}\n\n',
      );
      return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ turn: 6 }));
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const port = (server.address() as { port: number }).port;
  const api = createLiveApi(`http://127.0.0.1:${port}`, {
    user_id: "user-1",
    getToken: async () => "token-1",
  });
  try {
    const body = {
      client_message_id: "message-1",
      text: "why",
      attachments: [
        {
          kind: "repository_code" as const,
          label: "app.py · lines 469 to 470",
          text: "if not base or not user_id:\n    return []",
          source: { file: "app.py", first_line: 469, last_line: 470 },
        },
      ],
    };
    await api.send("w 1", body);
    await api.snapshot("w 1", 3);
    await api.file("w 1", "src/app.py");
    let stop: () => void = () => {};
    const text: string[] = [];
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        stop();
        reject(new Error("stream timed out"));
      }, 3000);
      stop = api.stream("w 1", {
        tutor: (e) => text.push(e.text),
        revision: (e) => {
          assert.equal(e.revision, 4);
          stop();
          clearTimeout(timer);
          resolve();
        },
        error: reject,
      });
    });
    assert.deepEqual(text, ["hello"]);
    assert.deepEqual(observed[0].body, body);
    assert.equal(observed[0].url, "/workspaces/w%201/messages");
    assert.equal(observed[1].url, "/workspaces/w%201?since=3");
    assert.equal(observed[2].url, "/workspaces/w%201/file?path=src%2Fapp.py");
    assert.equal(observed[3].url, "/workspaces/w%201/stream");
    observed.forEach((req) => {
      assert.equal(req.auth, "Bearer token-1");
      assert.equal(req.user, "user-1");
      assert.ok(!req.url.includes("token"));
    });
  } finally {
    server.closeAllConnections();
    server.close();
  }
});
