// Sample data for demo mode only. Task 3 and its turns follow the task 3 scenario in
// new_completly_desighn/LEGO.md §8–§10; the other tasks are placeholders for the ladder.
import type { LadderIssue, StoryKind } from "./types";

export interface CraftedBox {
  number: number;
  text: string;
}
export interface CraftedConcept {
  number: number;
  name: string;
  boxes: CraftedBox[];
}
export interface CraftedTask {
  id: string;
  number: number;
  title: string;
  goal: string;
  tier: string;
  files: string[];
  job: CraftedBox;
  concepts: CraftedConcept[];
  opening: string; // the tutor's first message when the task opens
}

// A line of the story: kind, text, depth, the issue in focus, picking up.
export type Line = [StoryKind, string, number, string | null, string?];

export interface Step {
  learner: string | null;
  tutor: string;
  tools?: string[];
  story: Line[];
  ticks?: number[];
  open_issue?: {
    id: string;
    number: number;
    title: string;
    parent_issue_id: string | null;
    status: LadderIssue["status"];
  };
  issue_status?: [string, LadderIssue["status"]][];
  where?: { issue_id: string | null; depth: number; you_are_here: string };
  close_task?: boolean;
}

export const WORKSPACE_NAME = "chatbot_final_version";

export const TASKS: CraftedTask[] = [
  {
    id: "task-1",
    number: 1,
    title: "trace one question through the chatbot",
    goal: "predict the chatbot's answer to one question, then check it",
    tier: "understand",
    files: ["app.py"],
    job: { number: 1, text: "predicts the answer to one question, then checks it" },
    concepts: [
      {
        number: 4,
        name: "tuple unpacking",
        boxes: [{ number: 2, text: "explains what line 610 unpacks" }],
      },
    ],
    opening:
      "Your first task: pick one question a recruiter might ask. Before you run it, predict what the chatbot answers.",
  },
  {
    id: "task-2",
    number: 2,
    title: "unknown labels need a fallback",
    goal: "a question with an unknown label gets a clear answer",
    tier: "first change",
    files: ["app.py"],
    job: { number: 1, text: "an unknown label gets a clear answer" },
    concepts: [
      {
        number: 5,
        name: "dict.get with a default",
        boxes: [{ number: 2, text: "uses .get with a default for a missing key" }],
      },
    ],
    opening:
      "Next: when a question comes with a label the app doesn't know, it crashes. Where does the app look the label up?",
  },
  {
    id: "task-3",
    number: 3,
    title: "guests always get the generic error",
    goal: "guests get a real answer again",
    tier: "debug",
    files: ["app.py"],
    job: { number: 1, text: "the fix works: a guest gets a real answer" },
    concepts: [
      {
        number: 17,
        name: "a broad except hides the real error",
        boxes: [{ number: 2, text: "finds the real error behind the generic message" }],
      },
      {
        number: 15,
        name: "loop variables outlive the loop",
        boxes: [{ number: 3, text: "explains why label is unbound for a guest" }],
      },
      {
        number: 13,
        name: "OpenAI tool calling",
        boxes: [{ number: 4, text: "explains what the label decides in the request" }],
      },
    ],
    opening:
      "Here's your task: as a guest, the chatbot always answers \"Une erreur s'est produite\". The goal: guests get a real answer. Your task sheet shows what you'll prove along the way. Where would you start?",
  },
  {
    id: "task-4",
    number: 4,
    title: "recruiters can filter offers by city",
    goal: "a recruiter who names a city sees only that city's offers",
    tier: "modify",
    files: ["app.py"],
    job: { number: 1, text: "a recruiter who names a city sees only that city's offers" },
    concepts: [
      {
        number: 6,
        name: "list comprehensions with a condition",
        boxes: [{ number: 2, text: "filters the offers in one comprehension" }],
      },
      {
        number: 13,
        name: "OpenAI tool calling",
        boxes: [{ number: 3, text: "adds the city to the tool's parameters" }],
      },
    ],
    opening:
      "You fixed the guest error. Next: recruiters want to filter offers by city. Where does the app build the list of offers it sends back?",
  },
  {
    id: "task-5",
    number: 5,
    title: "log every question a guest asks",
    goal: "every guest question is written to a log file",
    tier: "assemble",
    files: ["app.py"],
    job: { number: 1, text: "every guest question lands in the log file" },
    concepts: [
      {
        number: 8,
        name: "the logging module",
        boxes: [{ number: 2, text: "sets up a logger that writes to a file" }],
      },
    ],
    opening: "Next: the team wants to see what guests ask. Where would you record each question?",
  },
  {
    id: "task-6",
    number: 6,
    title: "conversations survive a restart",
    goal: "a conversation is still there after the app restarts",
    tier: "build",
    files: ["app.py"],
    job: { number: 1, text: "a conversation is still there after a restart" },
    concepts: [
      {
        number: 9,
        name: "SQLite with sqlite3",
        boxes: [{ number: 2, text: "stores and reads a conversation with sqlite3" }],
      },
    ],
    opening: "Last task: conversations disappear when the app restarts. Where do they live today?",
  },
];

// What happened in the two finished tasks, kept short.
export const HISTORY: { task_id: string; steps: Step[] }[] = [
  {
    task_id: "task-1",
    steps: [
      {
        learner: null,
        tutor: TASKS[0].opening,
        story: [["started", "trace one question through the chatbot", 0, null]],
      },
      {
        learner:
          "Line 610 unpacks the question into its label and the query. I predicted three recruiter offers, and that's what it answered.",
        tutor: "Prediction checked against a real run. That's the habit.",
        story: [
          ["ticked", "explains what line 610 unpacks", 0, null],
          ["ticked", "predicts the answer to one question, then checks it", 0, null],
          ["done", "trace one question through the chatbot", 0, null],
        ],
        ticks: [2, 1],
        close_task: true,
      },
    ],
  },
  {
    task_id: "task-2",
    steps: [
      {
        learner: null,
        tutor: TASKS[1].opening,
        story: [["started", "unknown labels need a fallback", 0, null]],
      },
      {
        learner:
          "It does TOOLS_BY_LABEL[label]. I changed it to TOOLS_BY_LABEL.get(label, []), and an unknown label now gets a plain answer.",
        tutor: "A default instead of a crash. Done.",
        story: [
          ["ticked", "uses .get with a default for a missing key", 0, null],
          ["ticked", "an unknown label gets a clear answer", 0, null],
          ["done", "a question with an unknown label gets a clear answer", 0, null],
        ],
        ticks: [2, 1],
        close_task: true,
      },
    ],
  },
];

const ISSUE_1 = "a loop variable only exists if the loop ran";
const ISSUE_2 = "why the loop on line 684 runs 0 times for a guest";
const ISSUE_3 = "how the test fakes OpenAI";
const TASK = "guests always get the generic error";

// Task 3, turn by turn. Demo mode starts after turn 5.
export const TASK_3_STEPS: Step[] = [
  {
    learner: null,
    tutor: TASKS[2].opening,
    story: [["started", TASK, 0, null]],
  },
  {
    learner:
      "Reproduced it. Same message every time as a guest. Where does this message even come from?",
    tutor:
      "Good, you can see it yourself. Now search the code for the exact text of that message. Which file and line does it come from?",
    story: [["did", "reproduced the bug as a guest", 0, null]],
  },
  {
    learner:
      "Line 824. It's inside `except Exception as e:` on line 821. So something crashes and this except swallows it?",
    tutor:
      "Exactly: that except hides whatever crashed. How could you see the real error it swallows? Try it in your editor.",
    tools: ["reading app.py, lines 815 to 830"],
    story: [["did", "found the except on line 821 that hides the crash", 0, null]],
  },
  {
    learner:
      "UnboundLocalError on `label`! But label is right there in the loop on line 684?! How can it not exist?",
    tutor:
      "That's the real error behind the message. Before app.py, try this in your editor:\n\n```py\ndef last(items):\n    for x in items: pass\n    return x\n```\n\nWhat do you predict `last([])` returns?",
    tools: ["reading concept 15 · loop variables outlive the loop"],
    ticks: [2],
    story: [
      ["ticked", "finds the real error behind the generic message", 0, null],
      ["found_a_gap", "label doesn't exist for a guest", 0, "issue-1"],
      ["went_to_learn_first", ISSUE_1, 0, "issue-1"],
    ],
    open_issue: { id: "issue-1", number: 1, title: ISSUE_1, parent_issue_id: null, status: "now" },
    where: { issue_id: "issue-1", depth: 1, you_are_here: ISSUE_1 },
  },
  {
    learner: "None? In JS it would be undefined.",
    tutor: "Good guess from JavaScript. Run it and see. What does Python actually say?",
    story: [["almost", "you expected None after an empty loop", 1, "issue-1"]],
  },
  {
    learner:
      "It crashes: UnboundLocalError, same as the app! But why would the loop on line 684 run 0 times for a guest?",
    tutor:
      "Let's trace it. Line 684 loops over a list. Where does that list come from for a guest? Follow it back.",
    tools: ["reading app.py, lines 680 to 690"],
    story: [
      ["did", "ran last([]) and saw the same error", 1, "issue-1"],
      ["needed_first", ISSUE_2, 1, "issue-2"],
    ],
    open_issue: { id: "issue-2", number: 2, title: ISSUE_2, parent_issue_id: "issue-1", status: "now" },
    issue_status: [["issue-1", "on_hold"]],
    where: { issue_id: "issue-2", depth: 2, you_are_here: ISSUE_2 },
  },
  {
    learner:
      "Lines 469–470: `if not base or not user_id: return []`. A guest has no user_id, so it returns an empty list.",
    tutor:
      "Right: for a guest the loop gets []. Now connect it: after a loop over [], what is label?",
    tools: ["reading app.py, lines 460 to 475"],
    story: [
      ["cleared", ISSUE_2, 2, "issue-2"],
      ["came_back", ISSUE_1, 1, "issue-1", "you get last([]) now; connect it to label"],
    ],
    issue_status: [["issue-2", "cleared"], ["issue-1", "now"]],
    where: { issue_id: "issue-1", depth: 1, you_are_here: ISSUE_1 },
  },
  {
    learner:
      "Nothing. It never gets assigned, exactly like x in last([]). Then line 722 reads label and crashes, and the except on line 821 hides it.",
    tutor:
      "That's it. Back to the task: you have the traceback, and you know why label is unbound. What should line 722 use instead?",
    story: [
      ["cleared", ISSUE_1, 1, "issue-1"],
      ["came_back", TASK, 0, null, "you have the traceback; line 722 reads label"],
    ],
    issue_status: [["issue-1", "cleared"]],
    where: { issue_id: null, depth: 0, you_are_here: TASK },
  },
  {
    learner:
      "`question_label`! Line 610 unpacks it from `user_query_operations`, and `QUESTION_LABELS` is {'recruiter', 'candidate', 'both'}. So line 722 should use question_label instead of label.",
    tutor: "Yes. Make that change in your editor, then try it as a guest. What happens now?",
    tools: ["reading app.py, lines 605 to 615"],
    ticks: [3],
    story: [
      ["ticked", "explains why label is unbound for a guest", 0, null],
      ["did", "named the fix: question_label on line 722", 0, null],
    ],
  },
  {
    learner:
      "It works as a guest now: it answered \"Voici nos offres de stage…\". Wait, how does the app's test talk to the chatbot without an OpenAI key?",
    tutor:
      "Short answer: the test swaps the real OpenAI client for a fake one, so it needs no key. I saved it for later. One box left: on line 722, what does the label decide in the request?",
    ticks: [1],
    story: [
      ["ticked", "the fix works: a guest gets a real answer", 0, null],
      ["saved_for_later", ISSUE_3, 0, "issue-3"],
    ],
    open_issue: {
      id: "issue-3",
      number: 3,
      title: ISSUE_3,
      parent_issue_id: null,
      status: "on_hold",
    },
  },
  {
    learner:
      "Whether the model gets the pricing tool. `tools` is the list of functions OpenAI is allowed to call, and candidates don't get the pricing one.",
    tutor:
      "Yes: the label decides whether the model gets the pricing tool. Every box is ticked, but one thing is still waiting before the next task: how the test fakes OpenAI. Open tests/conftest.py. Where does the test get its OpenAI client?",
    ticks: [4],
    story: [
      ["ticked", "explains what the label decides in the request", 0, null],
      ["picked_up", ISSUE_3, 0, "issue-3"],
    ],
    issue_status: [["issue-3", "now"]],
    where: { issue_id: "issue-3", depth: 1, you_are_here: ISSUE_3 },
  },
  {
    learner:
      "A fixture swaps app.client for FakeClient, which always returns a canned answer. So the test never calls OpenAI and needs no key.",
    tutor:
      "Exactly: a fake that returns canned answers. Nothing is waiting anymore, so this task is done: you can explain every step, from the hidden error to the empty loop to what the label decides. I wrote the path you took into your journey.",
    tools: ["reading tests/conftest.py"],
    story: [
      ["cleared", ISSUE_3, 1, "issue-3"],
      ["done", "guests get a real answer again", 0, null],
    ],
    issue_status: [["issue-3", "cleared"]],
    close_task: true,
  },
];
// The next step to play: turns 0 to 5 are already done.
export const TASK_3_START = 6;

const lines: string[] = Array(830).fill("");
const put = (at: number, text: string[]) =>
  text.forEach((line, i) => (lines[at - 1 + i] = line));
put(1, ["# app.py · a sample excerpt for demo mode: only the lines task 3 talks about"]);
put(12, ['QUESTION_LABELS = {"recruiter", "candidate", "both"}']);
put(468, [
  "def get_offers(base, user_id):",
  "    if not base or not user_id:",
  "        return []",
  "    return base.offers_for(user_id)",
]);
put(600, ["def answer(question, base, user_id):", "    try:"]);
put(610, ["        question_label, query = user_query_operations(question)"]);
put(683, ["        offers = get_offers(base, user_id)", "        for label in offers:", "            pass"]);
put(722, ["        tools = tools_for(label)", "        return ask_openai(query, tools=tools)"]);
put(821, [
  "    except Exception as e:",
  "        log(e)",
  "        # never show a crash to the user",
  "        return \"Une erreur s'est produite\"",
]);
const conftest = [
  "# tests/conftest.py · a sample excerpt for demo mode",
  "import pytest",
  "import app",
  "",
  "class FakeClient:",
  "    def create(self, **request):",
  '        return {"answer": "Voici nos offres de stage…"}',
  "",
  "@pytest.fixture(autouse=True)",
  "def fake_openai(monkeypatch):",
  '    monkeypatch.setattr(app, "client", FakeClient())',
  "",
];
export const FILES: Record<string, string> = {
  "app.py": lines.join("\n"),
  "tests/conftest.py": conftest.join("\n"),
};

export const SCRATCH = {
  name: "scratch.py",
  text: "def last(items):\n    for x in items: pass\n    return x\n\nprint(last([]))\n",
};
