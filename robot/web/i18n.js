/* Local-only language preference. No remote translation requests. */
const supportedLanguages = ["en", "zh"];
let language = "en";
try {
  language =
    localStorage.getItem("limo-console-language") ||
    (navigator.language.startsWith("zh") ? "zh" : "en");
} catch (_) {}
if (!supportedLanguages.includes(language)) language = "en";
const englishByChinese = Object.fromEntries(
  Object.entries(translations).map(([en, zh]) => [zh, en]),
);
const messagePrefixes = Object.keys(translations)
  .filter((key) => /[:：] $/.test(key))
  .sort((a, b) => b.length - a.length);
function t(source, values = []) {
  if (!source) return "";
  source = String(source);
  const canonical = englishByChinese[source] || source;
  let result =
    language === "zh" ? translations[canonical] || canonical : canonical;
  if (language === "zh" && !translations[canonical]) {
    const prefix = messagePrefixes.find((prefix) =>
      canonical.startsWith(prefix),
    );
    if (prefix) result = translations[prefix] + canonical.slice(prefix.length);
    result = result
      .replace(/Chassis reports error (\d+)/, "底盘报告故障 $1")
      .replace(
        /Chassis paused or not ready \(state (-?\d+)\); check the robot pause button/,
        "底盘暂停或未就绪（状态 $1）；请检查实体暂停按钮",
      );
  }
  return result.replace(/\{(\d+)\}/g, (match, index) =>
    values[index] === undefined ? match : String(values[index]),
  );
}
function applyLanguage(next) {
  if (!supportedLanguages.includes(next)) return;
  language = next;
  document.documentElement.lang = next === "zh" ? "zh-CN" : "en";
  try {
    localStorage.setItem("limo-console-language", next);
  } catch (_) {}
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  for (const [attribute, dataset] of [
    ["aria-label", "i18nAria"],
    ["alt", "i18nAlt"],
    ["placeholder", "i18nPlaceholder"],
  ]) {
    document
      .querySelectorAll(
        "[data-" +
          dataset.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase()) +
          "]",
      )
      .forEach((el) => el.setAttribute(attribute, t(el.dataset[dataset])));
  }
  document
    .querySelectorAll("[data-language]")
    .forEach((button) =>
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.language === next),
      ),
    );
  window.dispatchEvent(new Event("languagechange"));
}
document.querySelectorAll("[data-language]").forEach((button) => {
  button.onclick = () => applyLanguage(button.dataset.language);
});
applyLanguage(language);
