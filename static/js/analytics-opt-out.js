// Runs before the Umami tracker (templates/partials/analytics.html).
// Event names and their meaning: docs/analytics.md.
(function () {
  // ?notrack=1 switches this browser off, ?notrack=0 back on. "umami.keep"
  // remembers the explicit opt-in, so an operator who wants to see their own
  // traffic is not switched off again by excludeOperator() below.
  try {
    const flag = new URLSearchParams(window.location.search).get("notrack");
    if (flag === "1") {
      localStorage.setItem("umami.disabled", "1");
      localStorage.removeItem("umami.keep");
    } else if (flag === "0") {
      localStorage.removeItem("umami.disabled");
      localStorage.setItem("umami.keep", "1");
    }
  } catch (_) { /* storage unavailable */ }

  const CAMPAIGN_PARAM = /^(utm_(source|medium|campaign|content|term)|ref)$/;

  window.consensioAnalytics = {
    // The operator made about half of all runs; their browsers leave the
    // numbers as soon as /user_status says admin.
    excludeOperator() {
      try {
        if (localStorage.getItem("umami.keep") !== "1") localStorage.setItem("umami.disabled", "1");
      } catch (_) { /* storage unavailable */ }
    },
  };

  // Umami calls this (data-before-send) before every pageview and event.
  window.consensioBeforeSend = function (type, payload) {
    const agent = (window.navigator && window.navigator.userAgent) || "";
    if ((window.navigator && window.navigator.webdriver) || /HeadlessChrome|PhantomJS|Lighthouse/i.test(agent)) {
      return false;
    }
    // data-exclude-search drops the whole query string, which keeps tokens
    // from email links out of Umami. Campaign tags are the one part worth
    // keeping, so they are put back, and nothing else.
    try {
      const keep = new URLSearchParams();
      new URLSearchParams(window.location.search).forEach((value, key) => {
        // A forwarded link may carry an address in ?ref=; never keep one.
        if (CAMPAIGN_PARAM.test(key) && !String(value).includes("@")) keep.append(key, String(value).slice(0, 80));
      });
      const query = keep.toString();
      if (query && payload && typeof payload.url === "string" && payload.url.indexOf("?") === -1) {
        const hash = payload.url.indexOf("#");
        payload.url = hash === -1 ? `${payload.url}?${query}` : `${payload.url.slice(0, hash)}?${query}${payload.url.slice(hash)}`;
      }
    } catch (_) { /* keep the stripped URL */ }
    return payload;
  };

  // One event for every way into the app from a public page, so a funnel
  // needs one step instead of eight page-specific CTA names. Those names
  // keep firing for continuity.
  document.addEventListener("click", event => {
    const link = event.target && typeof event.target.closest === "function" ? event.target.closest("a[href]") : null;
    if (!link) return;
    let url;
    try { url = new URL(link.getAttribute("href"), window.location.href); } catch (_) { return; }
    const inApp = path => /^\/app(\/|$)/.test(path);
    if (url.origin !== window.location.origin || !inApp(url.pathname) || inApp(window.location.pathname)) return;
    const page = window.location.pathname === "/" ? "landing" : window.location.pathname.split("/")[1] || "landing";
    const data = { from: page === "s" ? "share" : page, demo: url.searchParams.get("demo") === "1" };
    const place = link.id || link.getAttribute("data-umami-event");
    if (place) data.place = place;
    if (window.umami && typeof window.umami.track === "function") window.umami.track("open_app", data);
  }, true);
})();
