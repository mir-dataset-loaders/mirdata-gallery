// Light mode only. The theme switches to dark mode when the system prefers it,
// but the gallery's colours are made for a light page. This runs before the
// theme starts (theme.js is deferred), so the theme reads darkMode = false.
function useLightMode() {
    try {
        localStorage.setItem("_x_darkMode", "false");
    } catch (e) {
        // no storage (e.g. blocked): removing the class below still works for this page
    }
    document.documentElement.classList.remove("dark");
}

useLightMode();
// The theme also follows system changes while the page is open; undo those too.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", useLightMode);
