// The one way a Watch's schedule is written: the sheet
// (watch-sheet.js), the card under an answer (agent-watch.js) and the
// Watches page (watch-dashboard.js) all say it the same way. Classic script;
// exports window.App.watchFields. Loads before all three.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

  function capitalize(text) {
    const value = String(text || "");
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function browserTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    } catch (_) {
      return "UTC";
    }
  }

  // A watch's time zone is named only when it is not the reader's own, and
  // as a place ("New York time"), never as "America/New_York".
  function timezoneCity(timezone, own = browserTimezone()) {
    const zone = String(timezone || "");
    if (!zone || zone === own) return "";
    if (/^(Etc\/)?(UTC|GMT|Universal|Zulu)$/i.test(zone)) return "UTC";
    return zone.split("/").pop().replace(/_/g, " ");
  }

  // "Weekly on Tuesday at 09:00 (New York time)", already in the reader's
  // language (App.t): one whole sentence per shape, since German says
  // "Jeden Dienstag um 09:00" (docs/i18n.md). The single words go by
  // "watch schedule": the plain "Daily" is the preset.
  const SCHEDULES = {
    daily: { alone: "Daily", at: "Daily at {time}" },
    weekly: { alone: "Weekly", at: "Weekly at {time}", on: "Weekly on {weekday}", onAt: "Weekly on {weekday} at {time}" },
    monthly: { alone: "Monthly", at: "Monthly at {time}" }
  };

  function scheduleLabel(watch, { own } = {}) {
    const interval = ["daily", "monthly"].includes(watch?.interval) ? watch.interval : "weekly";
    const words = SCHEDULES[interval];
    const weekday = interval === "weekly" && WEEKDAYS.includes(watch?.run_weekday) ? App.t(capitalize(watch.run_weekday)) : "";
    const time = watch?.run_time || "";
    const key = weekday ? (time ? words.onAt : words.on) : (time ? words.at : words.alone);
    const text = App.t(key, { weekday, time }, "watch schedule");
    const city = timezoneCity(watch?.timezone, own);
    if (!city) return text;
    return city === "UTC" ? text + " (UTC)" : App.t("{schedule} ({city} time)", { schedule: text, city }, "watch schedule");
  }

  App.watchFields = { scheduleLabel };
})();
