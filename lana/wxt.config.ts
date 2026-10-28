import { defineConfig } from 'wxt';

// See https://wxt.dev/api/reference/wxt/interfaces/inlineconfig.html
export default defineConfig({
  srcDir: 'src',
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Lana',
    description: 'You and your AI on the same page, learning faster together.',
    permissions: ['sidePanel', 'contextMenus', 'storage'],
    action: { default_title: 'Open Lana' },
    // The Goal Book web app may start and stop research mode.
    externally_connectable: {
      matches: ['https://agentic-tutor-lake.vercel.app/*', 'http://localhost:3000/*'],
    },
    commands: {
      'keep-selection': {
        suggested_key: { default: 'Ctrl+Shift+K', mac: 'Command+Shift+K' },
        description: 'Keep the selection with Lana',
      },
    },
  },
});
