import { toBackground, type AnnotateResult, type Envelope, type MarkResult, type Research, type ToPage } from '@/contract/messages';
import { capture, pageInfo, partOfHeading } from './capture';
import { labelResults } from './results';
import { createLayer } from './layer';
import { findHeading, findText } from './find';

// The page script: hidden inside every website. It never edits the site's own
// elements; everything Lana shows is drawn in its own layer (see layer.ts).

export default defineContentScript({
  matches: ['<all_urls>'],
  runAt: 'document_idle',
  main(ctx) {
    if (window.top !== window) return; // one Lana per tab: the top page only

    const layer = createLayer(ctx, {
      onKeep: () => void send('keep', 'selection-menu'),
      onAsk: () => void send('ask', 'selection-menu'),
    });

    // Off, Lana stays out of the way: no menu, no marks. It asks the background once, then follows its changes.
    let active = false;
    const follow = (research: Research) => {
      active = research.active;
      layer.enable(active);
    };
    void browser.runtime.sendMessage(toBackground({ type: 'page:research?' })).then((r) => r && follow(r as Research)).catch(() => {});

    // What the learner right-clicked last: an image, some code, a table.
    let lastTarget: Element | null = null;
    document.addEventListener('contextmenu', (e) => (lastTarget = e.target as Element), true);

    async function send(action: 'keep' | 'ask', source: 'selection-menu' | 'context-menu' | 'shortcut', imageUrl?: string) {
      if (!active) return;
      const taken = capture({ target: lastTarget, imageUrl });
      if (!taken) return;
      layer.hideSelectionMenu();
      layer.toast(action === 'keep' ? 'Kept' : 'Sent');
      await browser.runtime.sendMessage(toBackground({ type: 'page:captured', action, source, capture: taken }));
    }

    function answer(message: ToPage): unknown {
      switch (message.type) {
        case 'page:who-are-you':
          return pageInfo();
        case 'research:changed':
          follow(message.research);
          return { ok: true };
        case 'page:capture':
          void send(message.action, message.source, message.imageUrl);
          return { ok: true };
        case 'mark:point': {
          if (!active) return { found: false, reason: 'not-on-page' } satisfies MarkResult;
          const heading = findHeading(message.part);
          if (!heading) return { found: false, reason: 'not-on-page' } satisfies MarkResult;
          layer.point(heading);
          return { found: true } satisfies MarkResult;
        }
        case 'mark:highlight': {
          if (!active) return { found: false, reason: 'not-on-page' } satisfies MarkResult;
          const range = findText(message.text, layer.host);
          if (!range) return { found: false, reason: 'not-on-page' } satisfies MarkResult;
          layer.highlight(range, message.text);
          return { found: true } satisfies MarkResult;
        }
        case 'mark:clear':
          layer.clear();
          return { ok: true };
        case 'mark:annotate':
          if (!active) return { found: [] } satisfies AnnotateResult;
          return { found: layer.annotate(message.annotations) } satisfies AnnotateResult;
        case 'mark:focus':
          return { found: active && layer.focus(message.id) };
        case 'mark:results': {
          if (!active) return { labeled: [] };
          const found = labelResults(message.results);
          layer.results(found);
          return { labeled: found.map((r) => r.url) };
        }
        case 'pick:start':
          if (!active) return { ok: false };
          layer.pick((heading) => {
            void browser.runtime.sendMessage(toBackground({ type: 'page:picked', part: partOfHeading(heading), page: pageInfo() }));
          });
          return { ok: true };
        case 'pick:stop':
          layer.pick(null);
          return { ok: true };
      }
    }

    browser.runtime.onMessage.addListener((raw, _sender, sendResponse) => {
      const message = raw as Envelope;
      if (message.to !== 'page') return;
      sendResponse(answer(message));
    });

    // Tell the panel where the learner is, now and after every in-page navigation.
    let lastUrl = '';
    const announce = () => {
      if (location.href === lastUrl) return;
      lastUrl = location.href;
      layer.clear();
      void browser.runtime.sendMessage(toBackground({ type: 'page:opened', page: pageInfo() })).catch(() => {});
    };
    announce();
    ctx.setInterval(announce, 1000);
  },
});
