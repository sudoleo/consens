const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.resolve(process.env.VIDEO_OUT || path.join(ROOT, 'output'));
const FF = process.env.FFMPEG_PATH || require('@ffmpeg-installer/ffmpeg').path;

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium', '/usr/bin/chromium-browser',
  ];
  const executable = candidates.find(p => p && fs.existsSync(p));
  if (!executable) throw new Error('Install Chrome/Chromium or set CHROME_PATH to its executable.');
  return executable;
}

module.exports = { ROOT, OUT, FF, findChrome };
if (require.main === module) {
  if (process.argv.includes('--ffmpeg')) console.log(FF);
  else console.log(JSON.stringify({ chrome: findChrome(), ffmpeg: FF, output: OUT }, null, 2));
}
