import { defineConfig } from 'wxt';

// See https://wxt.dev/api/reference/wxt/interfaces/inlineconfig.html
export default defineConfig({
  srcDir: 'src',
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Agentic Search Companion',
    description:
      'A side panel that searches beside you: it sees the page you are on, points to where to look, and keeps what you find.',
    permissions: ['sidePanel'],
    action: { default_title: 'Open the search companion' },
  },
});
