// Front‑end logic for the Shih Tzu family potty training app

// Logging utility
const logger = {
  info: (...args) => console.log('[INFO]', new Date().toLocaleTimeString(), ...args),
  warn: (...args) => console.warn('[WARN]', new Date().toLocaleTimeString(), ...args),
  error: (...args) => console.error('[ERROR]', new Date().toLocaleTimeString(), ...args),
  debug: (...args) => console.log('[DEBUG]', new Date().toLocaleTimeString(), ...args)
};

// Debounce utility to prevent rapid-fire calls
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Throttle utility to limit function calls
function throttle(func, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// Helper to select elements
const $ = (selector) => document.querySelector(selector);

// State
let authToken = null;
let currentUser = null;
let isAdmin = false;

logger.info('🐕 Dog Training App - Client starting');

// PWA: register service worker if available
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      // First, unregister ALL old service workers
      const registrations = await navigator.serviceWorker.getRegistrations();
      for (const registration of registrations) {
        await registration.unregister();
      }
      // Then register the new one
      const registration = await navigator.serviceWorker.register('/service-worker.js');
      logger.info('Service worker registered');
      // Check for updates periodically
      setInterval(() => registration.update(), 60000);
    } catch (err) {
      logger.warn('Service worker error:', err);
    }
  });
}

// On DOM ready
document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const authSection = $('#authSection');
  const mainSection = $('#mainSection');
  const loginTab = $('#loginTab');
  const registerTab = $('#registerTab');
  const loginForm = $('#loginForm');
  const registerForm = $('#registerForm');
  const authError = $('#authError');
  const loginButton = $('#loginButton');
  const registerButton = $('#registerButton');
  const generateInviteButton = $('#generateInvite');
  const resetInviteButton = $('#resetInvite');
  const inviteAdminSection = $('#inviteAdminSection');
  const inviteList = $('#inviteList');
  const dogNameDisplay = $('#dogNameDisplay');
  const dogNameInput = $('#dogNameInput');
  const dogAgeInput = $('#dogAgeInput');
  const dogPhotoInput = $('#dogPhotoInput');
  const dogPhotoFile = $('#dogPhotoFile');
  const dogPhotoPreviewImg = $('#dogPhotoPreviewImg');
  const dogAvatarImg = $('#dogAvatarImg');
  let _pendingPhotoBase64 = null; // holds base64 string (without data: prefix)
  const dogAgeText = $('#dogAgeText');
  const ownerName = $('#ownerName');
  const editDogButton = $('#editDogButton');
  const dogEditSection = $('#dogEditSection');
  const saveDogButton = $('#saveDogButton');
  const cancelDogEdit = $('#cancelDogEdit');
  const familyTotalEl = $('#familyTotal');
  const familyWeeklyEl = $('#familyWeekly');
  const familyGoalProgress = $('#familyGoalProgress');
  const scoreTableBody = $('#scoreTable tbody');
  const userNameEl = $('#userName');
  const userEmailEl = $('#userEmail');
  const logoutButton = $('#logoutButton');
  const headerTotalPoints = $('#headerTotalPoints');
  const reminderBanner = $('#reminderBanner');
  const reminderText = $('#reminderText');
  const dismissReminder = $('#dismissReminder');
  const scheduleList = $('#scheduleList');
  const timelineList = $('#timelineList');
  const historyDate = $('#historyDate');
  const historyList = $('#historyList');
  const walkOverlay = $('#walkOverlay');
  const walkTimerEl = $('#walkTimer');
  const walkDogNameEl = $('#walkDogName');
  const endWalkButton = $('#endWalkButton');
  const walkOverlayPoop = $('#walkOverlayPoop');
  const walkOverlayPee = $('#walkOverlayPee');
  const walkOverlayTreat = $('#walkOverlayTreat');
  const adminSettingsSection = $('#adminSettingsSection');
  const resetScoresButton = $('#resetScoresButton');
  const clearEventsButton = $('#clearEventsButton');
  const settingsButton = $('#settingsButton');

  let walkTimerId = null;
  let walkStartTime = null;
  let currentSchedule = null;

  // Auth tab switching
  loginTab.addEventListener('click', () => {
    loginTab.classList.add('active');
    registerTab.classList.remove('active');
    loginForm.classList.remove('hidden');
    registerForm.classList.add('hidden');
    authError.textContent = '';
  });
  registerTab.addEventListener('click', () => {
    registerTab.classList.add('active');
    loginTab.classList.remove('active');
    registerForm.classList.remove('hidden');
    loginForm.classList.add('hidden');
    authError.textContent = '';
  });

  // Parse invite token from URL if present
  const urlParams = new URLSearchParams(window.location.search);
  const inviteParam = urlParams.get('invite');
  if (inviteParam) {
    // switch to register tab
    registerTab.click();
    $('#registerInvite').value = inviteParam;
  }

  // Persisted token?
  const storedToken = localStorage.getItem('authToken');
  if (storedToken) {
    authToken = storedToken;
    loadUser();
  } else {
    authSection.classList.remove('hidden');
  }

  // Login handler (email + password)
  loginButton.addEventListener('click', async () => {
    const email = $('#loginEmail').value.trim();
    const password = $('#loginPassword').value.trim();
    logger.info('Login attempt:', email);
    if (!email || !password) {
      authError.textContent = 'אנא מלא אימייל וסיסמה.';
      return;
    }
    try {
      const resp = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await resp.json();
      logger.debug('Login response:', data);
      if (!resp.ok) {
        logger.error('Login failed:', data.error);
        authError.textContent = data.error || 'שגיאה.';
        return;
      }
      authToken = data.token;
      localStorage.setItem('authToken', authToken);
      logger.info('Login successful, loading user data');
      await loadUser();
    } catch (err) {
      logger.error('Login network error:', err);
      authError.textContent = 'שגיאת רשת. נסה שוב.';
    }
  });

  // Register handler (name + email + password + optional invite)
  registerButton.addEventListener('click', async () => {
    const displayName = $('#registerName').value.trim();
    const email = $('#registerEmail').value.trim();
    const password = $('#registerPassword').value.trim();
    const inviteToken = $('#registerInvite').value.trim();
    if (!email || !password) {
      authError.textContent = 'אנא מלא אימייל וסיסמה.';
      return;
    }
    const body = { email, password };
    if (displayName) body.username = displayName;
    if (inviteToken) body.inviteToken = inviteToken;
    try {
      const resp = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await resp.json();
      if (!resp.ok) {
        authError.textContent = data.error || 'שגיאה.';
        return;
      }
      authToken = data.token;
      localStorage.setItem('authToken', authToken);
      await loadUser();
    } catch (err) {
      authError.textContent = 'שגיאת רשת. נסה שוב.';
    }
  });

  // Load user info and initialize app UI
  async function loadUser() {
    logger.info('Loading user data...');
    try {
      const resp = await fetch('/api/user', {
        method: 'GET',
        headers: { Authorization: 'Bearer ' + authToken }
      });
      const data = await resp.json();
      logger.debug('User data response:', data);
      if (!resp.ok) {
        // token invalid; clear
        logger.error('User data load failed:', data.error);
        localStorage.removeItem('authToken');
        authToken = null;
        authSection.classList.remove('hidden');
        mainSection.classList.add('hidden');
        authError.textContent = 'התחברות מחדש נדרשת.';
        return;
      }
      currentUser = data;
      isAdmin = !!data.isAdmin;
      logger.info(`User loaded: ${data.username}, household: ${data.householdId}, admin: ${isAdmin}`);
      // populate profile UI
      userNameEl.textContent = data.username;
      userEmailEl.textContent = data.email || '';
      ownerName.textContent = data.username;
      dogNameDisplay.textContent = data.dogName || 'ללא שם';
      dogNameInput.value = data.dogName || '';
      dogAgeInput.value =
        data.dogAgeMonths !== undefined && data.dogAgeMonths !== null
          ? String(data.dogAgeMonths)
          : '';
      dogPhotoInput.value = data.dogPhotoUrl || '';
      // show avatar image if available
      if (data.dogPhotoUrl) {
        try {
          dogAvatarImg.src = data.dogPhotoUrl;
          dogAvatarImg.style.display = '';
          const emoji = document.querySelector('.dog-emoji');
          if (emoji) emoji.style.display = 'none';
        } catch (e) {
          // ignore
        }
      }
      updateDogAgeText();
      const myRow = (data.scoreboard || []).find(
        (row) => row.userId === data.userId
      );
      headerTotalPoints.textContent = myRow?.totalPoints ?? myRow?.points ?? 0;
      // show invites list
      renderInvites(data.inviteTokens || []);
      // render members list (admins only will see promote/demote)
      renderMembers(data.members || []);
      // render scoreboard
      renderScoreboard(
        data.scoreboard || [],
        data.familyTotal || 0,
        data.familyWeeklyTotal || 0
      );
      // load today timeline & challenge
      await loadToday();
      authSection.classList.add('hidden');
      mainSection.classList.remove('hidden');
      inviteAdminSection.classList.toggle('hidden', !isAdmin);
      if (adminSettingsSection) {
        adminSettingsSection.classList.toggle('hidden', !isAdmin);
      }
      // Only show dog edit controls to admins
      if (editDogButton) {
        editDogButton.style.display = isAdmin ? '' : 'none';
      }
      if (dogEditSection && !isAdmin) {
        dogEditSection.classList.add('hidden');
      }
    } catch (err) {
      console.error(err);
    }
  }

  // Fetch members from server (used after login)
  async function fetchMembers() {
    if (!authToken) return;
    try {
      const resp = await fetch('/api/household/members', {
        method: 'GET',
        headers: { Authorization: 'Bearer ' + authToken }
      });
      if (!resp.ok) return;
      const data = await resp.json();
      renderMembers(data.members || []);
    } catch (e) {
      logger.warn('Failed to fetch members:', e);
    }
  }

  // Render household members and show promote/demote buttons for admins
  function renderMembers(members) {
    const memberList = $('#memberList');
    if (!memberList) return;
    memberList.innerHTML = '';
    members.forEach((m) => {
      const li = document.createElement('li');
      li.style.display = 'flex';
      li.style.justifyContent = 'space-between';
      li.style.alignItems = 'center';
      const name = document.createElement('span');
      name.textContent = m.username + (m.email ? ` (${m.email})` : '');
      const right = document.createElement('div');
      if (m.isAdmin) {
        const badge = document.createElement('small');
        badge.textContent = 'מנהל';
        badge.style.marginRight = '0.5rem';
        right.appendChild(badge);
      }
      if (isAdmin && m.id !== currentUser.userId) {
        const btn = document.createElement('button');
        btn.textContent = m.isAdmin ? 'הסר מנהל' : 'הפוך למנהל';
        btn.className = 'small-button';
        btn.addEventListener('click', async () => {
          try {
            const resp = await fetch(`/api/household/members/${m.id}/manager`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + authToken },
              body: JSON.stringify({ isAdmin: !m.isAdmin })
            });
            if (!resp.ok) {
              alert('שגיאה בעדכון זכויות');
              return;
            }
            const j = await resp.json();
            m.isAdmin = j.isAdmin;
            renderMembers(members);
          } catch (e) {
            alert('שגיאת רשת');
          }
        });
        right.appendChild(btn);
      }
      li.appendChild(name);
      li.appendChild(right);
      memberList.appendChild(li);
    });
  }

  // Render invite tokens
  function renderInvites(tokens) {
    inviteList.innerHTML = '';
    const base = window.location.origin + window.location.pathname;
    tokens.forEach((tokObj) => {
      // tokObj may be a string (legacy) or an object { token, linkedUsername }
      const token = typeof tokObj === 'string' ? tokObj : tokObj.token;
      const linked = typeof tokObj === 'string' ? null : tokObj.linkedUsername;

      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = token;

      // show linked username if available
      if (linked) {
        const linkedSpan = document.createElement('small');
        linkedSpan.textContent = ` - משויך: ${linked}`;
        linkedSpan.style.marginLeft = '0.6rem';
        span.appendChild(linkedSpan);
      }

      const linkButton = document.createElement('button');
      linkButton.textContent = 'העתק קישור';
      linkButton.addEventListener('click', () => {
        const url = `${base}?invite=${token}`;
        copyToClipboard(url);
        alert('קישור הועתק ללוח!');
      });
      li.appendChild(span);
      li.appendChild(linkButton);
      inviteList.appendChild(li);
    });
  }

  // Render scoreboard + family score
  function renderScoreboard(scoreboard, familyTotal, familyWeeklyTotal) {
    // Update family total text
    familyTotalEl.textContent = `סך הכל נקודות: ${familyTotal}`;
    familyWeeklyEl.textContent = `השבוע: ${familyWeeklyTotal}`;
    // Simple weekly family goal of 50 points
    const goal = 50;
    const pct = Math.max(0, Math.min(100, (familyWeeklyTotal / goal) * 100));
    familyGoalProgress.style.width = `${pct}%`;
    // Clear table body
    scoreTableBody.innerHTML = '';
    scoreboard.forEach((row, index) => {
      const tr = document.createElement('tr');
      const rankTd = document.createElement('td');
      rankTd.textContent = index + 1;
      const nameTd = document.createElement('td');
      nameTd.textContent = row.username;
      const pointsTd = document.createElement('td');
      pointsTd.textContent = row.totalPoints ?? row.points ?? 0;
      const weeklyTd = document.createElement('td');
      weeklyTd.textContent = row.weeklyPoints ?? 0;
      const streakTd = document.createElement('td');
      streakTd.textContent = row.streak ?? 0;
      tr.appendChild(rankTd);
      tr.appendChild(nameTd);
      tr.appendChild(pointsTd);
      tr.appendChild(weeklyTd);
      tr.appendChild(streakTd);
      scoreTableBody.appendChild(tr);
    });
  }

  // Copy to clipboard helper
  function copyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  }

  // Event buttons (quick actions)
  document.querySelectorAll('.actions-grid .action').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const type = btn.getAttribute('data-type');
      if (type === 'walk') {
        // Open the walk overlay immediately so the user always
        // sees the trip screen, even if saving the event fails.
        openWalkOverlay();
        await recordEvent('walk', btn);
        // Also create three scheduled walk placeholders for today (morning/afternoon/evening)
        try {
          scheduleThreeWalksForToday();
        } catch (e) {
          logger.warn('Failed to schedule three walks locally:', e);
        }
      } else {
        await recordEvent(type, btn);
      }
    });
  });

  function scheduleThreeWalksForToday() {
    const today = new Date();
    const key = `scheduledWalks-${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    // compute default times using current schedule fetched from server
    // We'll read the latest schedule by calling loadToday once synchronously isn't possible, so reuse computed defaults
    const defaults = {
      morningTs: Math.floor(computeRecommendedWalkTime('morning', {}).getTime() / 1000),
      afternoonTs: Math.floor(computeRecommendedWalkTime('afternoon', {}).getTime() / 1000),
      eveningTs: Math.floor(computeRecommendedWalkTime('evening', {}).getTime() / 1000),
    };
    localStorage.setItem(key, JSON.stringify(defaults));
    // merge into current UI by triggering loadToday which will read localStorage
    loadToday();
  }

  // Walk overlay internal buttons
  if (walkOverlayPoop) {
    walkOverlayPoop.addEventListener('click', async () => {
      walkOverlayPoop.disabled = true;
      const originalText = walkOverlayPoop.innerHTML;
      walkOverlayPoop.innerHTML = '<span class="emoji">✅</span><span>נרשם!</span>';
      await recordEvent('poop', walkOverlayPoop);
      setTimeout(() => {
        walkOverlayPoop.innerHTML = originalText;
        walkOverlayPoop.disabled = false;
      }, 1000);
    });
  }
  if (walkOverlayPee) {
    walkOverlayPee.addEventListener('click', async () => {
      walkOverlayPee.disabled = true;
      const originalText = walkOverlayPee.innerHTML;
      walkOverlayPee.innerHTML = '<span class="emoji">✅</span><span>נרשם!</span>';
      await recordEvent('pee', walkOverlayPee);
      setTimeout(() => {
        walkOverlayPee.innerHTML = originalText;
        walkOverlayPee.disabled = false;
      }, 1000);
    });
  }
  if (walkOverlayTreat) {
    walkOverlayTreat.addEventListener('click', async () => {
      walkOverlayTreat.disabled = true;
      const originalText = walkOverlayTreat.innerHTML;
      walkOverlayTreat.innerHTML = '<span class="emoji">✅</span><span>נרשם!</span>';
      await recordEvent('reward', walkOverlayTreat);
      setTimeout(() => {
        walkOverlayTreat.innerHTML = originalText;
        walkOverlayTreat.disabled = false;
      }, 1000);
    });
  }

  if (endWalkButton) {
    endWalkButton.addEventListener('click', () => {
      closeWalkOverlay();
    });
  }

  async function recordEvent(type, sourceButton) {
    logger.info(`Recording event: ${type}`);
    try {
      const resp = await fetch('/api/events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + authToken
        },
        body: JSON.stringify({ type })
      });
      const data = await resp.json();
      logger.debug('Event response:', data);
      if (resp.ok) {
        logger.info(`Event ${type} recorded successfully, new family total: ${data.familyTotal}`);
        renderScoreboard(
          data.scoreboard || [],
          data.familyTotal || 0,
          data.familyWeeklyTotal || 0
        );
        headerTotalPoints.textContent =
          data.scoreboard?.find((row) => row.userId === currentUser?.userId)
            ?.totalPoints || headerTotalPoints.textContent;
        const reminderKind = sourceButton?.getAttribute('data-reminder');
        if (reminderKind === 'treat') {
          showReminder('קחו חטיפים לפני שיוצאים לטיול 🦴');
        }
        if (type === 'pee' || type === 'poop') {
          showReminder('עכשיו נותנים חטיף גדול! 🌟');
        }
        await loadToday();
        return true;
      }
      logger.error('Event recording failed:', data);
      console.error('Event error:', data);
      alert(data.error || 'שגיאה ברישום האירוע.');
      return false;
    } catch (err) {
      logger.error('Event network error:', err);
      console.error('Network error:', err);
      alert('שגיאת רשת. ודא שהשרת פועל.');
      return false;
    }
  }

  // Edit dog profile toggle
  editDogButton.addEventListener('click', () => {
    if (!isAdmin) return; // extra safety: only admins can open edit UI
    dogEditSection.classList.remove('hidden');
    dogNameInput.focus();
  });
  cancelDogEdit.addEventListener('click', () => {
    dogEditSection.classList.add('hidden');
  });

  // Handle file selection: resize/crop to square and preview
  if (dogPhotoFile) {
    dogPhotoFile.addEventListener('change', async (evt) => {
      const f = evt.target.files && evt.target.files[0];
      if (!f) return;
      try {
        const dataUrl = await fileToDataUrl(f);
        const squared = await resizeImageToSquare(dataUrl, 300);
        // squared is a data URL; strip prefix for upload convenience
        const base64 = squared.split(',')[1];
        _pendingPhotoBase64 = base64;
        // preview
        dogPhotoPreviewImg.src = squared;
        dogPhotoPreviewImg.style.display = '';
        // clear URL input to avoid confusion
        dogPhotoInput.value = '';
      } catch (e) {
        alert('שגיאה בעיבוד התמונה');
      }
    });
  }
  saveDogButton.addEventListener('click', async () => {
    const newName = dogNameInput.value.trim();
    const ageVal = dogAgeInput.value.trim();
    const ageMonths = ageVal ? parseInt(ageVal, 10) : null;
    const photoUrl = dogPhotoInput.value.trim() || null;
    try {
      const resp = await fetch('/api/dog', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + authToken
        },
        body: JSON.stringify({
          dogName: newName,
          dogAgeMonths: ageMonths,
          dogPhotoUrl: photoUrl,
          // include base64 payload if user uploaded a file
          dogPhotoBase64: _pendingPhotoBase64
        })
      });
      const data = await resp.json();
      if (resp.ok) {
        dogNameDisplay.textContent = data.dogName || 'ללא שם';
        dogAgeInput.value =
          data.dogAgeMonths !== undefined && data.dogAgeMonths !== null
            ? String(data.dogAgeMonths)
            : '';
        dogPhotoInput.value = data.dogPhotoUrl || '';
        updateDogAgeText();
        renderScoreboard(
          data.scoreboard || [],
          data.familyTotal || 0,
          data.familyWeeklyTotal || 0
        );
        dogEditSection.classList.add('hidden');
      } else {
        alert(data.error || 'שגיאה בעדכון השם.');
      }
    } catch (err) {
      alert('שגיאת רשת.');
    }
  });

  // Generate invite token (admin only)
  if (generateInviteButton) {
    generateInviteButton.addEventListener('click', async () => {
    try {
      const resp = await fetch('/api/invite', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + authToken }
      });
      const data = await resp.json();
      if (resp.ok) {
        renderInvites(data.inviteTokens || []);
      } else {
        alert(data.error || 'שגיאה ביצירת הזמנה.');
      }
    } catch (err) {
      alert('שגיאת רשת.');
    }
    });
  }

  // Reset invites (revoke + regenerate)
  if (resetInviteButton) {
    resetInviteButton.addEventListener('click', async () => {
      try {
        const resp = await fetch('/api/invite/reset', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + authToken }
        });
        const data = await resp.json();
        if (resp.ok) {
          renderInvites(data.inviteTokens || []);
        } else {
          alert(data.error || 'שגיאה באיפוס ההזמנות.');
        }
      } catch (err) {
        alert('שגיאת רשת.');
      }
    });

  // Utilities for image processing
  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(fr.result);
      fr.onerror = reject;
      fr.readAsDataURL(file);
    });
  }

  async function resizeImageToSquare(dataUrl, size) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        // draw to canvas, crop to center square
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        const w = img.width;
        const h = img.height;
        const side = Math.min(w, h);
        const sx = Math.floor((w - side) / 2);
        const sy = Math.floor((h - side) / 2);
        ctx.drawImage(img, sx, sy, side, side, 0, 0, size, size);
        // export as JPEG to reduce size
        const out = canvas.toDataURL('image/jpeg', 0.85);
        resolve(out);
      };
      img.onerror = reject;
      img.src = dataUrl;
    });
  }
  }

  // Settings button - go to family tab
  if (settingsButton) {
    settingsButton.addEventListener('click', () => {
      const familyTabButton = document.querySelector('[data-tab="familyTab"]');
      if (familyTabButton) {
        familyTabButton.click();
      }
    });
  }

  // Logout
  logoutButton.addEventListener('click', () => {
    localStorage.removeItem('authToken');
    authToken = null;
    currentUser = null;
    mainSection.classList.add('hidden');
    authSection.classList.remove('hidden');
    $('#loginEmail').value = '';
    $('#loginPassword').value = '';
    $('#registerName').value = '';
    $('#registerEmail').value = '';
    $('#registerPassword').value = '';
    $('#registerInvite').value = '';
    authError.textContent = '';
  });

  // Tabs behaviour
  document.querySelectorAll('.tabs .tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      document.querySelectorAll('.tabs .tab').forEach((t) =>
        t.classList.remove('active')
      );
      tab.classList.add('active');
      document.querySelectorAll('.tab-panel').forEach((panel) => {
        panel.classList.toggle('hidden', panel.id !== target);
      });
    });
  });

  // Reminder helpers
  function showReminder(text) {
    reminderText.textContent = text;
    reminderBanner.classList.remove('hidden');
  }

  dismissReminder.addEventListener('click', () => {
    reminderBanner.classList.add('hidden');
  });

  // Walk overlay helpers
  function openWalkOverlay() {
    if (!walkOverlay) return;
    walkDogNameEl.textContent = dogNameDisplay.textContent || 'שיצו שלי';
    walkStartTime = Date.now();
    updateWalkTimer();
    if (walkTimerId) clearInterval(walkTimerId);
    walkTimerId = setInterval(updateWalkTimer, 1000);
    walkOverlay.classList.remove('hidden');
  }

  function closeWalkOverlay() {
    if (!walkOverlay) return;
    walkOverlay.classList.add('hidden');
    if (walkTimerId) {
      clearInterval(walkTimerId);
      walkTimerId = null;
    }
  }

  function updateWalkTimer() {
    if (!walkStartTime || !walkTimerEl) return;
    const diffSec = Math.floor((Date.now() - walkStartTime) / 1000);
    const minutes = String(Math.floor(diffSec / 60)).padStart(2, '0');
    const seconds = String(diffSec % 60).padStart(2, '0');
    walkTimerEl.textContent = `${minutes}:${seconds}`;
  }

  // Dog age display (client-side only for now)
  function updateDogAgeText() {
    const ageMonths = parseInt(dogAgeInput.value || '0', 10);
    if (!ageMonths) {
      dogAgeText.classList.add('hidden');
      return;
    }
    const years = Math.floor(ageMonths / 12);
    const months = ageMonths % 12;
    let text = '';
    if (years) text += `${years} שנים `;
    if (months) text += `${months} חודשים`;
    dogAgeText.textContent = `גיל: ${text.trim()}`;
    dogAgeText.classList.remove('hidden');
  }

  dogAgeInput.addEventListener('input', updateDogAgeText);

  // Load today's events and update timeline + schedule + challenge
  let loadTodayInProgress = false;
  async function loadTodayCore() {
    if (!authToken) {
      logger.log('No auth token, skipping loadToday');
      return;
    }
    if (loadTodayInProgress) {
      logger.debug('loadToday already in progress, skipping');
      return;
    }
    loadTodayInProgress = true;
    try {
      const resp = await fetch('/api/today', {
        headers: { Authorization: 'Bearer ' + authToken }
      });
      const data = await resp.json();
      if (!resp.ok) {
        logger.error('API error:', data);
        return;
      }
      // merge any locally scheduled walks for today
      try {
        const today = new Date();
        const key = `scheduledWalks-${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
        currentSchedule = data.schedule || {};
        const raw = localStorage.getItem(key);
        if (raw) {
          const local = JSON.parse(raw);
          data.schedule = data.schedule || {};
          // store local scheduled times separately from 'hasWalkX' which means completed
          if (local.morningTs) data.schedule.localMorningTs = local.morningTs;
          if (local.afternoonTs) data.schedule.localAfternoonTs = local.afternoonTs;
          if (local.eveningTs) data.schedule.localEveningTs = local.eveningTs;
          // also expose feed timestamps if absent (don't overwrite real ones)
          if (!data.schedule.feedMorningTs && local.feedMorningTs) data.schedule.feedMorningTs = local.feedMorningTs;
          if (!data.schedule.feedEveningTs && local.feedEveningTs) data.schedule.feedEveningTs = local.feedEveningTs;
        }
      } catch (e) {
        logger.warn('Failed to merge local scheduled walks:', e);
      }

      renderTimeline(data.events || []);
      updateSchedule(currentSchedule);
    } catch (e) {
      logger.error('Error loading today:', e);
    } finally {
      loadTodayInProgress = false;
    }
  }
  
  // Throttle to max once per 300ms
  const loadToday = throttle(loadTodayCore, 300);
  
  // Expose for debugging
  window.testLoadToday = loadToday;

  function renderTimeline(events) {
    if (!timelineList) {
      logger.error('❌ Timeline list element (#timelineList) NOT FOUND in DOM!');
      return;
    }
    timelineList.innerHTML = '';
    
    if (!events || events.length === 0) {
      const emptyDiv = document.createElement('div');
      emptyDiv.textContent = 'עדיין לא היו אירועים היום';
      emptyDiv.style.color = '#999';
      emptyDiv.style.textAlign = 'center';
      emptyDiv.style.padding = '20px';
      timelineList.appendChild(emptyDiv);
      return;
    }
    
    const sorted = [...events].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    sorted.forEach((e, index) => {
      if (index < 3) {
        logger.debug(`  Event ${index}: ${e.type} at ${formatTime(e.timestamp)} by ${e.username}`);
      }
      
      const row = document.createElement('div');
      row.className = `timeline-row event-${e.type}`;
      
      // Add delete button
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-event-btn';
      deleteBtn.textContent = '×';
      deleteBtn.title = 'מחק אירוע';
      deleteBtn.onclick = async (evt) => {
        evt.stopPropagation();
        if (confirm('למחוק אירוע זה?')) {
          await deleteEvent(e.id);
        }
      };
      row.appendChild(deleteBtn);
      
      const rightDiv = document.createElement('div');
      rightDiv.className = 'timeline-row-right';
      
      const iconSpan = document.createElement('span');
      iconSpan.className = 'timeline-event-icon';
      iconSpan.textContent = eventIcon(e.type);
      
      const labelSpan = document.createElement('span');
      labelSpan.className = 'timeline-event-label';
      labelSpan.textContent = eventLabel(e.type);
      
      const userSpan = document.createElement('span');
      userSpan.className = 'timeline-event-user';
      if (e.username) {
        userSpan.textContent = e.username;
      }
      
      rightDiv.appendChild(iconSpan);
      rightDiv.appendChild(labelSpan);
      rightDiv.appendChild(userSpan);
      
      const timeSpan = document.createElement('span');
      timeSpan.className = 'timeline-event-time';
      timeSpan.textContent = formatTime(e.timestamp);
      
      row.appendChild(rightDiv);
      row.appendChild(timeSpan);
      
      timelineList.appendChild(row);
    });
  }
  
  function eventIcon(type) {
    const icons = {
      walk: '🚶',
      walk_morning: '🌅',
      walk_afternoon: '🌤️',
      walk_evening: '🌙',
      poop: '💩',
      pee: '💧',
      reward: '🦴',
      accident: '❌',
      feed_morning: '🍖',
      feed_evening: '🍖'
    };
    return icons[type] || '📝';
  }

  function updateSchedule(schedule) {
    if (!scheduleList) return;
    scheduleList.innerHTML = '';
    // Build richer schedule: morning, afternoon, evening walks and feed flags
    // Prefer explicit local scheduled times if present, otherwise compute recommendations
    const morningWalkTime = schedule.localMorningTs ? new Date(schedule.localMorningTs * 1000) : computeRecommendedWalkTime('morning', schedule);
    const afternoonWalkTime = schedule.localAfternoonTs ? new Date(schedule.localAfternoonTs * 1000) : computeRecommendedWalkTime('afternoon', schedule);
    const eveningWalkTime = schedule.localEveningTs ? new Date(schedule.localEveningTs * 1000) : computeRecommendedWalkTime('evening', schedule);

    const items = [
      { icon: '🍖', label: 'אוכל בוקר', done: !!schedule.hasMorningFeed },
      { icon: '🚶‍♀️', label: 'בוקר', time: morningWalkTime, done: !!schedule.hasWalkMorning },
      { icon: '🚶‍♀️', label: 'צהריים', time: afternoonWalkTime, done: !!schedule.hasWalkAfternoon },
      { icon: '🚶‍♀️', label: 'ערב', time: eveningWalkTime, done: !!schedule.hasWalkEvening },
      { icon: '💧', label: 'פיפי', done: !!schedule.hasPee },
      { icon: '💩', label: 'קקי', done: !!schedule.hasPoop },
      { icon: '🍖', label: 'אוכל ערב', done: !!schedule.hasEveningFeed }
    ];

    items.forEach(item => {
      const li = document.createElement('li');
      const left = document.createElement('div');
      left.style.display = 'flex';
      left.style.alignItems = 'center';
      const labelSpan = document.createElement('span');
      labelSpan.textContent = `${item.icon} ${item.label}`;
      left.appendChild(labelSpan);
      if (item.time) {
        const timeSpan = document.createElement('span');
        timeSpan.style.marginLeft = '8px';
        timeSpan.style.fontSize = '0.9rem';
        timeSpan.style.color = '#555';
        timeSpan.textContent = `— ${formatTimeLocal(item.time)}`;
        left.appendChild(timeSpan);
      }
      const checkSpan = document.createElement('span');
      checkSpan.className = 'check-pill';
      checkSpan.textContent = item.done ? '✔' : '✖';
      if (item.done) checkSpan.classList.add('done');
      li.appendChild(left);
      li.appendChild(checkSpan);
      scheduleList.appendChild(li);
    });

    // After updating UI, (re)schedule notifications for feed events
    try {
      scheduleNotificationsForFeeds();
    } catch (e) {
      logger.error('Failed to schedule notifications:', e);
    }
  }

  // Helper: format a JS Date (or timestamp seconds) to hh:mm
  function formatTimeLocal(tsOrDate) {
    const d = tsOrDate instanceof Date ? tsOrDate : new Date((tsOrDate || 0) * 1000);
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  }

  // Compute recommended walk times (Date objects) for morning/afternoon/evening
  function computeRecommendedWalkTime(part, schedule) {
    const now = new Date();
    // If schedule contains explicit feed timestamps, prefer them
    // schedule may include fields like feedMorningTs/feedEveningTs set by loadToday
    if (part === 'morning') {
      if (schedule.feedMorningTs) return new Date(schedule.feedMorningTs * 1000 + 2 * 3600 * 1000);
      // default 09:00 today
      return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 9, 0, 0);
    }
    if (part === 'afternoon') {
      if (schedule.feedMorningTs) return new Date(schedule.feedMorningTs * 1000 + 6 * 3600 * 1000);
      return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 14, 0, 0);
    }
    if (part === 'evening') {
      if (schedule.feedEveningTs) return new Date(schedule.feedEveningTs * 1000 + 2 * 3600 * 1000);
      return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 19, 0, 0);
    }
    return null;
  }

  // Schedule in-page notifications 1.5 hours after any feed events (if permission granted)
  let _scheduledNotificationIds = [];
  function scheduleNotificationsForFeeds() {
    // clear previous timers
    _scheduledNotificationIds.forEach(id => clearTimeout(id));
    _scheduledNotificationIds = [];

    // We will request Notification permission if not granted yet
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      Notification.requestPermission().then(() => scheduleNotificationsForFeeds());
      return;
    }
    if (Notification.permission !== 'granted') return;

    // Use cached schedule (set by loadToday) when possible to avoid extra network calls
    const dataSchedule = currentSchedule || {};
    // If authToken and no cached schedule, we skip scheduling to avoid another network call
    if (!dataSchedule) return;
    const feedMorningTs = dataSchedule.feedMorningTs;
    const feedEveningTs = dataSchedule.feedEveningTs;
    [[feedMorningTs, 'feed_morning'], [feedEveningTs, 'feed_evening']].forEach(([ts, typ]) => {
      if (!ts) return;
      const notifTs = ts + 90 * 60; // 1.5 hours after feed (seconds)
      const msDelay = notifTs * 1000 - Date.now();
      if (msDelay <= 0) return;
      const id = setTimeout(() => {
        const walkLabel = typ === 'feed_morning' ? 'טיול בוקר' : 'טיול ערב';
        new Notification('זמן לטיול', { body: `בעוד חצי שעה בערך — ${walkLabel} מגיע!` });
        showReminder(`${walkLabel} — זמן לטיול בקרוב`);
      }, msDelay);
      _scheduledNotificationIds.push(id);
    });
  }

  function eventLabel(type) {
    switch (type) {
      case 'feed_morning':
        return 'אוכל בוקר';
      case 'walk_morning':
        return 'טיול בוקר';
      case 'walk_afternoon':
        return 'טיול צהריים';
      case 'walk_evening':
        return 'טיול ערב';
      case 'feed_evening':
        return 'אוכל ערב';
      case 'walk':
        return 'טיול';
      case 'pee':
        return 'פיפי';
      case 'poop':
        return 'קקי';
      case 'reward':
        return 'חטיף';
      case 'accident':
        return 'פספוס בבית';
      default:
        return type;
    }
  }

  function formatTime(ts) {
    const d = new Date(ts * 1000);
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  }

  // Calendar / history: load events for chosen date
  if (historyDate) {
    // default to today in local timezone
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    historyDate.value = `${yyyy}-${mm}-${dd}`;
    loadHistoryForDate(historyDate.value);

    historyDate.addEventListener('change', () => {
      if (historyDate.value) {
        loadHistoryForDate(historyDate.value);
      }
    });
  }

  async function loadHistoryForDate(dateStr) {
    if (!authToken || !dateStr) return;
    try {
      const resp = await fetch(`/api/history?date=${encodeURIComponent(dateStr)}`, {
        headers: { Authorization: 'Bearer ' + authToken }
      });
      const data = await resp.json();
      if (!resp.ok) return;
      renderHistory(data.events || []);
      // Also update schedule based on selected date events
      const schedule = {
        hasMorningFeed: data.events.some(e => e.type === 'feed_morning'),
        hasEveningFeed: data.events.some(e => e.type === 'feed_evening'),
        hasWalk: data.events.some(e => e.type === 'walk'),
        hasPee: data.events.some(e => e.type === 'pee'),
        hasPoop: data.events.some(e => e.type === 'poop')
      };
      updateSchedule(schedule);
    } catch (e) {
      // ignore
    }
  }

  function renderHistory(events) {
    historyList.innerHTML = '';
    
    if (!events || events.length === 0) {
      const emptyDiv = document.createElement('div');
      emptyDiv.textContent = 'לא נמצאו אירועים בתאריך זה';
      emptyDiv.style.color = '#999';
      emptyDiv.style.textAlign = 'center';
      emptyDiv.style.padding = '20px';
      historyList.appendChild(emptyDiv);
      return;
    }
    
    const sorted = [...events].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    sorted.forEach(e => {
      const row = document.createElement('div');
      row.className = `timeline-row event-${e.type}`;
      
      const rightDiv = document.createElement('div');
      rightDiv.className = 'timeline-row-right';
      
      const iconSpan = document.createElement('span');
      iconSpan.className = 'timeline-event-icon';
      iconSpan.textContent = eventIcon(e.type);
      
      const labelSpan = document.createElement('span');
      labelSpan.className = 'timeline-event-label';
      labelSpan.textContent = eventLabel(e.type);
      
      const userSpan = document.createElement('span');
      userSpan.className = 'timeline-event-user';
      if (e.username) {
        userSpan.textContent = e.username;
      }
      
      rightDiv.appendChild(iconSpan);
      rightDiv.appendChild(labelSpan);
      rightDiv.appendChild(userSpan);
      
      const timeSpan = document.createElement('span');
      timeSpan.className = 'timeline-event-time';
      timeSpan.textContent = formatTime(e.timestamp);
      
      row.appendChild(rightDiv);
      row.appendChild(timeSpan);
      
      historyList.appendChild(row);
    });
  }

  // Delete single event
  async function deleteEvent(eventId) {
    logger.info(`Deleting event: ${eventId}`);
    try {
      const resp = await fetch(`/api/events/${eventId}`, {
        method: 'DELETE',
        headers: { Authorization: 'Bearer ' + authToken }
      });
      const data = await resp.json();
      if (resp.ok) {
        logger.info('Event deleted successfully');
        renderScoreboard(
          data.scoreboard || [],
          data.familyTotal || 0,
          data.familyWeeklyTotal || 0
        );
        headerTotalPoints.textContent =
          data.scoreboard?.find((row) => row.userId === currentUser?.userId)
            ?.totalPoints || headerTotalPoints.textContent;
        await loadToday();
      } else {
        alert(data.error || 'שגיאה במחיקת האירוע');
      }
    } catch (err) {
      logger.error('Delete event error:', err);
      alert('שגיאת רשת');
    }
  }

  // Admin: Reset all scores
  if (resetScoresButton) {
    resetScoresButton.addEventListener('click', async () => {
      if (!confirm('האם אתה בטוח? פעולה זו תמחק את כל האירועים והנקודות ולא ניתן לבטל אותה!')) {
        return;
      }
      if (!confirm('בטוח בטוח? זה ימחק הכל!')) {
        return;
      }
      try {
        const resp = await fetch('/api/admin/reset-scores', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + authToken }
        });
        const data = await resp.json();
        if (resp.ok) {
          alert(data.message || 'כל הנקודות אופסו');
          // Refresh scoreboard and timeline only (not full loadUser)
          renderScoreboard(data.scoreboard || [], data.familyTotal || 0, data.familyWeeklyTotal || 0);
          headerTotalPoints.textContent = '0';
          await loadToday();
        } else {
          alert(data.error || 'שגיאה');
        }
      } catch (err) {
        alert('שגיאת רשת');
      }
    });
  }

  // Admin: Clear all events
  if (clearEventsButton) {
    clearEventsButton.addEventListener('click', async () => {
      if (!confirm('האם למחוק את כל האירועים? פעולה זו לא ניתנת לביטול!')) {
        return;
      }
      if (!confirm('בטוח בטוח? כל האירועים יימחקו!')) {
        return;
      }
      try {
        const resp = await fetch('/api/admin/clear-events', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + authToken }
        });
        const data = await resp.json();
        if (resp.ok) {
          alert(data.message || 'כל האירועים נמחקו');
          // Refresh scoreboard and timeline only
          renderScoreboard(data.scoreboard || [], data.familyTotal || 0, data.familyWeeklyTotal || 0);
          headerTotalPoints.textContent = '0';
          await loadToday();
        } else {
          alert(data.error || 'שגיאה');
        }
      } catch (err) {
        alert('שגיאת רשת');
      }
    });
  }
});