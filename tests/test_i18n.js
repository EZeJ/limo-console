const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web = path.join(__dirname, "../robot/web");
const context = vm.createContext({
  navigator: { language: "en-US" },
  localStorage: { getItem: () => null, setItem: () => {} },
  document: { documentElement: {}, querySelectorAll: () => [] },
  window: { dispatchEvent: () => {} },
  Event: class Event {},
});
vm.runInContext(
  fs.readFileSync(path.join(web, "messages.js"), "utf8"),
  context,
);
vm.runInContext(fs.readFileSync(path.join(web, "i18n.js"), "utf8"), context);
const run = (code) => vm.runInContext(code, context);
assert.equal(run("t('Stopped')"), "Stopped");
run("applyLanguage('zh')");
assert.equal(run("t('Stopped')"), "已停止");
assert.equal(run("t('Goal ({0}, {1}) m', [1.25, -2])"), "目标 (1.25, -2) m");
assert.equal(run("t('Map saved: room_01')"), "地图已保存：room_01");
assert.equal(run("t('Chassis reports error 12')"), "底盘报告故障 12");
assert.equal(run("document.documentElement.lang"), "zh-CN");
run("applyLanguage('en')");
assert.equal(run("t('已停止')"), "Stopped");
assert.equal(
  run("t('Turning speed must be between 0 and 2.00 rad/s.')"),
  "Turning speed must be between 0 and 2.00 rad/s.",
);
const html = ["index.html", "data.html"].map(name => fs.readFileSync(path.join(web, name), "utf8")).join("\n");
const app = ["app.js", "recording.js", "data.js"].map(name => fs.readFileSync(path.join(web, name), "utf8")).join("\n");
const keys = [
  ...html.matchAll(/data-i18n(?:-aria|-alt|-placeholder)?="([^"]+)"/g),
].map((m) => m[1]);
keys.push(
  ...[...app.matchAll(/\bt\((["'])((?:\\.|(?!\1).)*?)\1/g)].map((m) => m[2]),
);
for (const key of keys)
  assert.ok(
    run(`Object.hasOwn(translations, ${JSON.stringify(key)})`),
    "Missing translation: " + key,
  );
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
assert.equal(ids.length, new Set(ids).size, "Duplicate DOM IDs");
for (const match of app.matchAll(/\$\(['"]#([A-Za-z][A-Za-z0-9]*)['"]\)/g))
  assert.ok(ids.includes(match[1]), "Missing DOM target: " + match[1]);
assert.ok(
  !/[\u4e00-\u9fff]/.test(app),
  "Keep translated UI copy in messages.js",
);
console.log(
  "Localization, placeholders, language switching, and DOM wiring passed.",
);
