const http = require('node:http'), fs = require('node:fs');
const allowed = new Set(['/tutor.html', '/scan_stage.html', '/sidebar_sample.html']);
http.createServer((req, res) => { if (!allowed.has(req.url)) { res.writeHead(404); res.end(); return; } res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end(fs.readFileSync(req.url.slice(1))); }).listen(3002, '127.0.0.1');
