import type { Browser } from 'wxt/browser';
import {
  RESEARCH_OFF,
  toPage,
  toPanel,
  type CaptureAction,
  type CaptureSource,
  type Envelope,
  type FromApp,
  type FromPage,
  type FromPanel,
  type MarkResult,
  type PageInfo,
  type PanelStart,
  type Research,
  type ToPage,
  type ToPanel,
} from '@/contract/messages';

// The background is the hub: the page script and the panel only talk to it.
// It owns research mode, and what needs Chrome's own APIs: the toolbar icon,
// the right-click menu, the keyboard shortcut and the side panel.

const MENU_KEEP = 'lana-keep';
const MENU_ASK = 'lana-ask';
const COMMAND_KEEP = 'keep-selection';
const ACCENT = '#4f7290';

/** Messages for the panel that arrived while it was closed. */
const waiting: ToPanel[] = [];

/** Research mode, kept for the browser session: the service worker may sleep between events. */
let research: Research = RESEARCH_OFF;
const loaded = browser.storage.session.get('research').then((s) => {
  if (s.research) research = s.research as Research;
});

export default defineBackground(() => {
  // Clicking the toolbar icon opens the side panel beside the page.
  void browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

  browser.runtime.onInstalled.addListener(() => {
    browser.contextMenus.removeAll(() => {
      browser.contextMenus.create({ id: MENU_KEEP, title: 'Keep with Lana', contexts: ['selection', 'image', 'page'], visible: false });
      browser.contextMenus.create({ id: MENU_ASK, title: 'Ask Lana about this', contexts: ['selection', 'image', 'page'], visible: false });
      void loaded.then(showResearch);
    });
  });
  browser.runtime.onStartup.addListener(() => void loaded.then(showResearch));

  browser.contextMenus.onClicked.addListener((info, tab) => {
    if (!tab?.id || !research.active) return;
    const action: CaptureAction = info.menuItemId === MENU_ASK ? 'ask' : 'keep';
    // Opening the panel needs the click itself, so it comes before anything awaited.
    void browser.sidePanel.open({ tabId: tab.id });
    void askPageToCapture(tab.id, action, 'context-menu', info.srcUrl);
  });

  browser.commands.onCommand.addListener((command, tab) => {
    if (command !== COMMAND_KEEP || !tab?.id || !research.active) return;
    void browser.sidePanel.open({ tabId: tab.id });
    void askPageToCapture(tab.id, 'keep', 'shortcut');
  });

  // When the learner moves to another tab, or a page finishes loading, the panel follows.
  browser.tabs.onActivated.addListener(({ tabId }) => void reportPage(tabId));
  browser.tabs.onUpdated.addListener((tabId, change, tab) => {
    if (change.status === 'complete' && tab.active) void reportPage(tabId);
  });

  browser.runtime.onMessage.addListener((raw, sender, sendResponse) => {
    const message = raw as Envelope;
    if (message.to !== 'background') return;
    void handle(message, sender).then(sendResponse);
    return true; // the answer comes later
  });

  // The Goal Book web app starts and stops research mode (see externally_connectable in wxt.config.ts).
  browser.runtime.onMessageExternal.addListener((raw, _sender, sendResponse) => {
    const message = raw as FromApp;
    const done =
      message.type === 'research:start'
        ? setResearch({ active: true, goal: message.goal, question: message.question, startedAt: Date.now() })
        : setResearch(RESEARCH_OFF);
    void done.then(() => sendResponse({ ok: true }));
    return true;
  });
});

async function handle(message: FromPage | FromPanel, sender: Browser.runtime.MessageSender): Promise<unknown> {
  await loaded;
  switch (message.type) {
    case 'page:research?':
      return research;
    case 'page:opened':
      if (sender.tab?.active) await sendToPanel({ type: 'panel:page', page: message.page });
      return;
    case 'page:picked':
      await sendToPanel({ type: 'panel:picked', part: message.part, page: message.page });
      return;
    case 'panel:open': {
      const tab = await activeTab();
      if (tab?.id) await browser.tabs.update(tab.id, { url: message.url });
      return;
    }
    case 'page:captured':
      if (!research.active) return;
      await sendToPanel({ type: 'panel:captured', action: message.action, source: message.source, capture: message.capture });
      return;
    case 'panel:ready': {
      const tab = await activeTab();
      if (tab?.id) void reportPage(tab.id);
      return { research, waiting: waiting.splice(0) } satisfies PanelStart;
    }
    case 'panel:start-research':
      await setResearch({ active: true, goal: research.goal, question: message.question, startedAt: Date.now() });
      return research;
    case 'panel:stop-research':
      await setResearch(RESEARCH_OFF);
      return research;
    case 'panel:to-page': {
      const tab = await activeTab();
      if (!tab?.id) return { found: false, reason: 'no-page-script' } satisfies MarkResult;
      return sendToPage(tab.id, message.message);
    }
  }
}

/** Research mode changes everything at once: storage, icon, menu, every tab, the panel. */
async function setResearch(next: Research) {
  research = next;
  await browser.storage.session.set({ research });
  showResearch();
  const tabs = await browser.tabs.query({});
  for (const tab of tabs) if (tab.id) void sendToPage(tab.id, { type: 'research:changed', research });
  await sendToPanel({ type: 'panel:research', research });
}

/** The icon carries a dot while research mode is on; the right-click entries exist only then. */
function showResearch() {
  void browser.action.setBadgeBackgroundColor({ color: ACCENT });
  void browser.action.setBadgeText({ text: research.active ? ' ' : '' });
  void browser.contextMenus.update(MENU_KEEP, { visible: research.active }).catch(() => {});
  void browser.contextMenus.update(MENU_ASK, { visible: research.active }).catch(() => {});
}

async function activeTab() {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function sendToPage(tabId: number, message: ToPage): Promise<unknown> {
  try {
    return await browser.tabs.sendMessage(tabId, toPage(message));
  } catch {
    // No page script here: chrome:// pages, the Web Store, PDFs, or a tab opened before Lana was installed.
    return { found: false, reason: 'no-page-script' } satisfies MarkResult;
  }
}

async function sendToPanel(message: ToPanel) {
  try {
    await browser.runtime.sendMessage(toPanel(message));
  } catch {
    // The panel is closed: keep what was taken until it opens.
    if (message.type === 'panel:captured') waiting.push(message);
  }
}

async function reportPage(tabId: number) {
  const page = (await sendToPage(tabId, { type: 'page:who-are-you' })) as PageInfo | MarkResult;
  if (page && 'url' in page) await sendToPanel({ type: 'panel:page', page });
  else await sendToPanel({ type: 'panel:page-unavailable' });
}

async function askPageToCapture(tabId: number, action: CaptureAction, source: CaptureSource, imageUrl?: string) {
  await sendToPage(tabId, { type: 'page:capture', action, source, imageUrl });
}
