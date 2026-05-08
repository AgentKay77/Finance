// Service worker registration + offline indicator.
// The mutation queue described in the project plan will hook in here later.
(function () {
  "use strict";

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function (err) {
        console.warn("Service worker registration failed:", err);
      });
    });
  }

  var banner = document.getElementById("offline-banner");
  function updateOnlineStatus() {
    if (!banner) return;
    if (navigator.onLine) {
      banner.setAttribute("hidden", "");
    } else {
      banner.removeAttribute("hidden");
    }
  }
  window.addEventListener("online", updateOnlineStatus);
  window.addEventListener("offline", updateOnlineStatus);
  updateOnlineStatus();
})();
