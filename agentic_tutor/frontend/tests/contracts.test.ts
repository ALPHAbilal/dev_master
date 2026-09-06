import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { createLiveApi } from "../lib/api/live";
import { createStubApi } from "../lib/api/stub";
import { editKey } from "../lib/editor";
test("stub aside is idempotent, preserves the graded turn, and publishes the anchor and refs", async () => {
  const api = createStubApi(),
    driver = await api.resume();
  const body = {
    request_id: "test-request",
    unit_id: driver.unit_id!,
    question: "Why append?",
    refs: [
      {
        kind: "test" as const,
        label: "test.py",
        snippet: "append(x)",
        source: { editor_id: "test", text: "append(x)" },
      },
    ],
  };
  const ack = await api.aside(driver.journey_id, body);
  assert.deepEqual(await api.aside(driver.journey_id, body), ack);
  const update = await api.snapshot(driver.journey_id);
  assert.equal(
    update.snapshot!.conversation.filter((m) => m.id === ack.learner_message_id)
      .length,
    1,
  );
  assert.deepEqual(
    update.snapshot!.conversation.find((m) => m.id === ack.learner_message_id)!
      .refs,
    body.refs,
  );
  assert.ok(
    update.snapshot!.lifecycle.some(
      (e) => e.event_type === "aside" && e.payload?.thread_id === ack.thread_id,
    ),
  );
  assert.equal((await api.resume()).turn_id, driver.turn_id);
  assert.equal(
    (
      await api.snapshot(
        driver.journey_id,
        (await api.snapshot(driver.journey_id)).revision,
      )
    ).snapshot,
    null,
  );
});
test("workspace concurrency and editor indentation preserve content and selection", async () => {
  const api = createStubApi();
  await api.workspace({ expected_revision: 0, content: "first" });
  await assert.rejects(
    api.workspace({ expected_revision: 0, content: "overwrite" }),
    /Workspace changed/,
  );
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
test("live HTTP and EventSource use Bearer headers, exact bodies, and revision query", async () => {
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
        'event: token\ndata: {"turn_id":"turn-1","text":"hello"}\n\nevent: revision\ndata: {"revision":4}\n\n',
      );
      return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ operation: "aside" }));
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
      request_id: "request",
      unit_id: 3,
      question: "why",
      origin_message_id: 4,
    };
    await api.aside(1, body);
    await api.snapshot(1, 3);
    let stop: () => void = () => {};
    const token: string[] = [];
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        stop();
        reject(new Error("SSE timed out"));
      }, 3000);
      stop = api.stream(1, {
        token: (e) => token.push(e.text),
        revision: (e) => {
          assert.equal(e.revision, 4);
          stop();
          clearTimeout(timer);
          resolve();
        },
        error: reject,
      });
    });
    assert.deepEqual(token, ["hello"]);
    assert.deepEqual(observed[0].body, body);
    assert.equal(observed[1].url, "/journey/1?since=3");
    assert.equal(observed[2].url, "/journey/1/stream");
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
