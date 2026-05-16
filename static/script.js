// ─── PAGE NAVIGATION ───────────────────────────────────────────────
function showPage(page) {
  document.getElementById('page-home').style.display     = 'none';
  document.getElementById('page-login').style.display    = 'none';
  document.getElementById('page-register').style.display = 'none';
  document.getElementById('page-' + page).style.display  = 'block';
  window.scrollTo(0, 0);

  if (page === 'home') {
    setTimeout(startTyping, 100);
  }
}

// ─── TYPING ANIMATION ──────────────────────────────────────────────
var typedText   = 'Sit-in Monitoring System';
var typingIndex = 0;
var typingTimer = null;

function startTyping() {
  var el = document.getElementById('typed-text');
  if (!el) return;
  el.textContent = '';
  typingIndex = 0;
  clearInterval(typingTimer);

  typingTimer = setInterval(function() {
    if (typingIndex < typedText.length) {
      el.textContent += typedText.charAt(typingIndex);
      typingIndex++;
    } else {
      clearInterval(typingTimer);
    }
  }, 80);
}

window.onload = function() {
  setTimeout(startTyping, 100);
};
// Dark mode toggle (global)
function initGlobalDarkMode() {
  const isDark = localStorage.getItem('darkMode') === 'true';
  if (isDark) document.body.classList.add('dark-mode');
  const toggle = document.getElementById('darkModeToggle');
  if (toggle) {
    toggle.addEventListener('click', (e) => {
      e.preventDefault();
      document.body.classList.toggle('dark-mode');
      localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
    });
  }
}
document.addEventListener('DOMContentLoaded', initGlobalDarkMode);