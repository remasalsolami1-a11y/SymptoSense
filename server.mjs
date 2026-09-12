import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const port = Number(process.env.PORT || 3000);
const root = join(process.cwd(), 'dist');
const types = {
  '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.json':'application/json; charset=utf-8', '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg',
  '.svg':'image/svg+xml', '.ico':'image/x-icon', '.pdf':'application/pdf', '.woff':'font/woff', '.woff2':'font/woff2'
};

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === '/') pathname = '/index.html';
    let file = normalize(join(root, pathname));
    if (!file.startsWith(normalize(root))) throw new Error('bad path');
    try {
      const s = await stat(file);
      if (s.isDirectory()) file = join(file, 'index.html');
    } catch {
      if (!extname(file)) file = join(file, 'index.html');
    }
    const body = await readFile(file);
    res.writeHead(200, {
      'Content-Type': types[extname(file).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': extname(file).toLowerCase() === '.html' ? 'no-cache, no-store, must-revalidate' : 'public, max-age=3600'
    });
    res.end(body);
  } catch {
    res.writeHead(404, {'Content-Type':'text/plain; charset=utf-8'});
    res.end('Not Found');
  }
});
server.listen(port, '0.0.0.0', () => console.log(`Hedayaat exact-report site on ${port}`));
