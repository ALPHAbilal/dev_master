import { defineConfig } from 'wxt';

// See https://wxt.dev/api/reference/wxt/interfaces/inlineconfig.html
export default defineConfig({
  srcDir: 'src',
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Lana',
    description: 'You and your AI on the same page, learning faster together.',
    permissions: ['sidePanel'],
    action: { default_title: 'Open Lana' },
  },
});
