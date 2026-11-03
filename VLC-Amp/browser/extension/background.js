// Play in VLC Amp: turn a page, link or video into a vlc-amp: link. The vlc-amp: handler that Setup
// registers (browser/vlc-amp-url.ps1 on Windows, browser/vlc-amp-url.py on Linux) resolves it with yt-dlp
// and plays it in VLC. The browser asks once whether to open the handler ("Always allow" stops the question).
// Made for Chrome (also Edge, Brave, Vivaldi: the same extension API).
const api = chrome;

const MENUS = [
  { id: "video", title: "Play in VLC Amp" },
  { id: "audio", title: "Play audio only in VLC Amp" },
];

api.runtime.onInstalled.addListener(() => {
  api.contextMenus.removeAll(() => {
    for (const m of MENUS) {
      api.contextMenus.create({ id: m.id, title: m.title, contexts: ["page", "link", "video", "audio", "frame"] });
    }
  });
});

const isWeb = (u) => typeof u === "string" && /^https?:\/\//i.test(u);

// a right-clicked link first, then the <video> / <audio> source (not a blob: of a site's own player), then the page
function pick(info, tab) {
  return [info.linkUrl, info.srcUrl, info.frameUrl, info.pageUrl, tab && tab.url].find(isWeb);
}

function play(url, mode, tab) {
  if (!url) return;
  const link = "vlc-amp:play?mode=" + mode + "&url=" + encodeURIComponent(url);
  // navigating the tab to an external scheme opens the handler and leaves the page as it is
  if (tab && tab.id >= 0) api.tabs.update(tab.id, { url: link });
  else api.tabs.create({ url: link });
}

api.contextMenus.onClicked.addListener((info, tab) => play(pick(info, tab), info.menuItemId, tab));
api.action.onClicked.addListener((tab) => play(isWeb(tab.url) ? tab.url : null, "video", tab));
