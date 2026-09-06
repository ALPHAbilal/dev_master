// One-time, deterministic migration of design tokens and the small reference fixture.
const fs = require('node:fs');
const vm = require('node:vm');
for (const [file, scope] of [['tutor', 'tutor-screen'], ['scan_stage', 'scan-screen']]) {
  const html = fs.readFileSync(`${file}.html`, 'utf8');
  const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  fs.mkdirSync('app', { recursive: true });
  fs.writeFileSync(`app/${file}.css`, `/* Ported verbatim from ${file}.html; scoped to prevent the two token systems colliding. */\n@scope (.${scope}) {\n${css.replace(/:root/g, ':scope').replace(/^html\s*\{/gm, ':scope {').replace(/^body\s*\{/gm, ':scope {')}\n}\n`);
}
const html = fs.readFileSync('tutor.html', 'utf8');
const between = (start, end) => html.slice(html.indexOf(start), html.indexOf(end, html.indexOf(start)));
const source = [between('const CODEBASES =', '/* Each stream'), between('const STREAM =', '/* ── Sidebar'), between('const UNITS=', '/* render one line'), between('const FILES =', 'let currentFile'), between('const EDITOR_FILES =', 'const INDENT=')].join('\n');
fs.mkdirSync('lib/api', { recursive: true });
fs.writeFileSync('lib/api/demo.json', JSON.stringify(vm.runInNewContext(source + '\nJSON.parse(JSON.stringify({CODEBASES,STREAM,UNITS,FILES,EDITOR_FILES}))'), null, 2));
