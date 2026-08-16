/* ══════════════════════════════════════════════════════════════
   新手導覽（Onboarding Tour）
   一個不依賴攝影機、可重複觀看的「聚光燈」式功能導覽，
   依序介紹主選單、右上角所有系統圖示與 AI 教練，
   讓新玩家在正式開始遊戲前，先認識所有功能入口。
   ══════════════════════════════════════════════════════════════ */

const TOUR_STEPS = [
  { target: null,
    zh: { icon:'👋', title:'歡迎來到 123木頭人 PRO！', desc:'讓我們花 1 分鐘認識所有功能。導覽隨時可以按「跳過」結束，之後也能點右上角的 🧭，或到「設定」重新查看一次。' },
    en: { icon:'👋', title:'Welcome to 123 Statue PRO!', desc:'Let’s spend a minute walking through every feature. You can skip anytime, and replay this tour later from the 🧭 icon or Settings.' } },

  { target: '#btn-start-game',
    zh: { icon:'▶️', title:'開始遊戲', desc:'依序選擇角色、模式、難度後，就會進入攝影機姿勢偵測遊戲。' },
    en: { icon:'▶️', title:'Start Game', desc:'Pick a character, mode, and difficulty, then jump into the camera-based posture game.' } },

  { target: '#btn-watch-ad',
    zh: { icon:'🎬', title:'看廣告領金幣', desc:'點一下模擬廣告，立即免費領取 500 🪙，金幣可以在商城購買造型。' },
    en: { icon:'🎬', title:'Watch Ad for Coins', desc:'Watch a mock ad to instantly earn 500 🪙, spendable in the shop.' } },

  { target: '#coin-display',
    zh: { icon:'🪙', title:'我的金幣', desc:'這裡顯示你目前擁有的金幣總數，遊戲結束後領取的獎勵也會加進來。' },
    en: { icon:'🪙', title:'My Coins', desc:'Your current coin balance — rewards collected after each round get added here.' } },

  { target: '#nav-signin',
    zh: { icon:'📅', title:'每日簽到', desc:'每天登入點一次就能領金幣，連續簽到獎勵更豐富，別忘記天天來看看。' },
    en: { icon:'📅', title:'Daily Check-in', desc:'Tap once a day for coins — consecutive check-ins earn bigger rewards.' } },

  { target: '#nav-quests',
    zh: { icon:'🎯', title:'每日／每週任務', desc:'完成指定的遊戲任務（例如玩滿幾場、拿到幾分）可以額外領取金幣獎勵。' },
    en: { icon:'🎯', title:'Daily / Weekly Quests', desc:'Complete goals like playing N rounds or hitting a score target for bonus coins.' } },

  { target: '#nav-achievements',
    zh: { icon:'🏅', title:'成就徽章', desc:'達成特定里程碑（例如連續好姿勢、總遊玩次數）會解鎖專屬徽章。' },
    en: { icon:'🏅', title:'Achievements', desc:'Unlock badges by hitting milestones like posture streaks or total play count.' } },

  { target: '#nav-challenge',
    zh: { icon:'🤝', title:'好友挑戰', desc:'遊戲結束後可以產生挑戰碼分享給朋友，邀請他們來比拚分數。' },
    en: { icon:'🤝', title:'Friend Challenge', desc:'After a round, generate a challenge code to share and compete with friends.' } },

  { target: '#nav-shop',
    zh: { icon:'🛒', title:'角色商城', desc:'用金幣解鎖新角色、動作軌跡特效與頭飾，讓遊戲畫面更有個人風格。' },
    en: { icon:'🛒', title:'Shop', desc:'Spend coins on new characters, trail effects, and hats to personalize your game.' } },

  { target: '#nav-board',
    zh: { icon:'🏆', title:'排行榜', desc:'查看歷史最高分紀錄，可依「本賽季／通關／無限／限時」模式篩選。' },
    en: { icon:'🏆', title:'Leaderboard', desc:'View top scores, filterable by season, classic, infinite, or timed mode.' } },

  { target: '#nav-tutorial',
    zh: { icon:'📜', title:'遊戲規則說明', desc:'這裡有紅綠燈規則的詳細圖解（站➔坐➔站➔墊腳），正式上場前建議先看一次。' },
    en: { icon:'📜', title:'Game Rules', desc:'Detailed traffic-light rules (stand → sit → stand → tiptoe) — worth a look before your first run.' } },

  { target: '#nav-legal',
    zh: { icon:'🔒', title:'隱私權與安全聲明', desc:'說明攝影機影像如何被使用與保護，以及運動安全提醒，請務必詳閱。' },
    en: { icon:'🔒', title:'Privacy & Safety', desc:'How camera data is used and protected, plus exercise safety notes — please read carefully.' } },

  { target: '#phonecam-btn',
    zh: { icon:'🤳', title:'手機鏡頭連線（測試版）', desc:'沒有電腦鏡頭嗎？可以用手機掃描 QR Code，把手機當作偵測畫面的鏡頭。' },
    en: { icon:'🤳', title:'Phone Camera (Beta)', desc:'No webcam? Scan a QR code to use your phone as the detection camera instead.' } },

  { target: '#nav-settings',
    zh: { icon:'⚙️', title:'遊戲設定', desc:'這裡可以切換中英文介面、開關遊戲音效與背景粒子特效。' },
    en: { icon:'⚙️', title:'Settings', desc:'Switch language, toggle sound effects, and toggle the background particle effect.' } },

  { target: '#nav-contact',
    zh: { icon:'✉️', title:'聯絡我們', desc:'有任何建議、問題或錯誤回報，都可以透過這裡直接留言給我們。' },
    en: { icon:'✉️', title:'Contact Us', desc:'Send us feedback, questions, or bug reports directly from here.' } },

  { target: '#ai-chat-btn',
    zh: { icon:'🤖', title:'AI 教練', desc:'隨時點擊這裡詢問遊戲規則、坐站訓練好處或高分技巧，AI 教練會即時回覆你。' },
    en: { icon:'🤖', title:'AI Coach', desc:'Ask about game rules, the benefits of sit-to-stand training, or scoring tips anytime.' } },

  { target: null,
    zh: { icon:'🚀', title:'準備好了嗎？', desc:'點擊「開始遊戲」，依序選好角色、模式、難度，跟著紅綠燈完成站➔坐➔站➔墊腳，就能開始你的第一場訓練！這份導覽隨時可以在右上角 🧭 或「設定」中重新查看。' },
    en: { icon:'🚀', title:'Ready to go?', desc:'Tap "Start Game", pick a character/mode/difficulty, and follow the traffic light through stand → sit → stand → tiptoe. Replay this tour anytime via the 🧭 icon or Settings.' } }
];

let tourIdx = 0;

function tourLang() {
  return (typeof gameSettings !== 'undefined' && gameSettings.lang) || window.currentLang || 'zh-TW';
}

function ensureTourStyles() {
  if (document.getElementById('tour-style')) return;
  const style = document.createElement('style');
  style.id = 'tour-style';
  style.textContent = `
    #tour-mask{position:fixed;inset:0;z-index:10050;background:transparent;}
    #tour-spotlight{position:fixed;z-index:10051;pointer-events:none;border-radius:14px;
      border:2px solid var(--blue2);box-shadow:0 0 0 9999px rgba(6,14,28,.86);
      transition:top .35s ease,left .35s ease,width .35s ease,height .35s ease;}
    #tour-card{position:fixed;z-index:10052;background:var(--card);border:1.5px solid var(--border);
      border-radius:14px;padding:18px 20px;width:300px;box-shadow:0 14px 44px rgba(0,0,0,.55);
      animation:tourFadeIn .25s ease;}
    @keyframes tourFadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
    #tour-card .tour-nav-btn{padding:6px 14px;font-size:.8em;}
  `;
  document.head.appendChild(style);
}

function tourCloseOverlays() {
  document.querySelectorAll('.overlay-modal.on').forEach(el => el.classList.remove('on'));
  const legal = document.getElementById('ov-legal');
  if (legal && !legal.classList.contains('off') && typeof hasAgreedToLegal === 'function' && hasAgreedToLegal()) {
    legal.classList.add('off');
  }
  const settings = document.getElementById('ov-settings');
  if (settings) settings.classList.add('off');
}

function tourKeyHandler(e) {
  if (e.key === 'Escape') skipTour();
  else if (e.key === 'ArrowRight') tourGoNext();
  else if (e.key === 'ArrowLeft' && tourIdx > 0) renderTourStep(tourIdx - 1);
}

function positionTour(step) {
  const spotlight = document.getElementById('tour-spotlight');
  const card = document.getElementById('tour-card');
  if (!step.target) {
    spotlight.style.display = 'none';
    card.style.top = '50%'; card.style.left = '50%'; card.style.transform = 'translate(-50%,-50%)';
    return;
  }
  const el = document.querySelector(step.target);
  if (!el) {
    spotlight.style.display = 'none';
    card.style.top = '50%'; card.style.left = '50%'; card.style.transform = 'translate(-50%,-50%)';
    return;
  }
  card.style.transform = 'none';
  spotlight.style.display = 'block';
  const pad = 10;
  const r = el.getBoundingClientRect();
  spotlight.style.top = (r.top - pad) + 'px';
  spotlight.style.left = (r.left - pad) + 'px';
  spotlight.style.width = (r.width + pad * 2) + 'px';
  spotlight.style.height = (r.height + pad * 2) + 'px';

  // getBoundingClientRect() forces a synchronous layout, so this reads the
  // just-rendered card size without needing a rAF round-trip (avoids a flash).
  const cr = card.getBoundingClientRect();
  let top = r.bottom + pad + 10;
  let left = r.left + r.width / 2 - cr.width / 2;
  if (top + cr.height > window.innerHeight - 10) top = r.top - cr.height - pad - 10;
  if (top < 10) top = 10;
  if (left < 10) left = 10;
  if (left + cr.width > window.innerWidth - 10) left = window.innerWidth - 10 - cr.width;
  card.style.top = top + 'px';
  card.style.left = left + 'px';
}

function tourGoNext() {
  if (tourIdx >= TOUR_STEPS.length - 1) finishTour();
  else renderTourStep(tourIdx + 1);
}

function renderTourStep(idx) {
  tourIdx = idx;
  const step = TOUR_STEPS[idx];
  const lang = tourLang();
  const t = lang === 'en' ? step.en : step.zh;
  const isFirst = idx === 0, isLast = idx === TOUR_STEPS.length - 1;
  const card = document.getElementById('tour-card');
  card.innerHTML = `
    <div style="font-size:.7em;font-weight:700;letter-spacing:1px;color:var(--dim);margin-bottom:6px;">${idx + 1} / ${TOUR_STEPS.length}</div>
    <div style="font-size:1.05em;font-weight:800;color:var(--blue2);margin-bottom:6px;">${t.icon} ${t.title}</div>
    <div style="font-size:.85em;color:var(--text);line-height:1.65;margin-bottom:14px;">${t.desc}</div>
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
      <button id="tour-skip-btn" style="background:none;border:none;color:var(--dim);font-size:.76em;cursor:pointer;text-decoration:underline;padding:4px 0;">${lang === 'en' ? 'Skip tour' : '跳過導覽'}</button>
      <div style="display:flex;gap:8px;">
        ${!isFirst ? `<button id="tour-prev-btn" class="btn btn-ghost tour-nav-btn">${lang === 'en' ? 'Back' : '上一步'}</button>` : ''}
        <button id="tour-next-btn" class="btn btn-blue tour-nav-btn">${isLast ? (lang === 'en' ? "Let's go!" : '開始探索！') : (lang === 'en' ? 'Next' : '下一步')}</button>
      </div>
    </div>
  `;
  document.getElementById('tour-skip-btn').onclick = skipTour;
  const prevBtn = document.getElementById('tour-prev-btn');
  if (prevBtn) prevBtn.onclick = () => renderTourStep(idx - 1);
  document.getElementById('tour-next-btn').onclick = tourGoNext;
  positionTour(step);
}

function startTour(force) {
  if (document.getElementById('tour-mask')) return; // already running
  if (typeof goTo === 'function') goTo('scr-menu');
  tourCloseOverlays();
  ensureTourStyles();

  const mask = document.createElement('div'); mask.id = 'tour-mask';
  const spotlight = document.createElement('div'); spotlight.id = 'tour-spotlight';
  const card = document.createElement('div'); card.id = 'tour-card';
  document.body.appendChild(mask);
  document.body.appendChild(spotlight);
  document.body.appendChild(card);

  document.addEventListener('keydown', tourKeyHandler);
  if (typeof playSfx === 'function') { try { playSfx('click'); } catch (e) {} }
  renderTourStep(0);
}

function endTour() {
  ['tour-mask', 'tour-spotlight', 'tour-card'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
  document.removeEventListener('keydown', tourKeyHandler);
}

function markTourSeen() {
  try {
    const s = (typeof loadSave === 'function') ? loadSave() : {};
    s.tourSeen = true;
    if (typeof writeSave === 'function') writeSave(s);
  } catch (e) {}
}

function skipTour() {
  endTour();
  markTourSeen();
}

function finishTour() {
  endTour();
  markTourSeen();
  if (typeof showToast === 'function') {
    showToast(tourLang() === 'en' ? '🎉 Tour complete — have fun!' : '🎉 導覽完成，祝你玩得開心！', 'var(--green)');
  }
}

function maybeAutoStartTour() {
  try {
    const s = (typeof loadSave === 'function') ? loadSave() : {};
    if (s.tourSeen) return;
    if (typeof hasAgreedToLegal === 'function' && !hasAgreedToLegal()) return;
    setTimeout(() => { if (!document.getElementById('tour-mask')) startTour(false); }, 800);
  } catch (e) {}
}

window.addEventListener('DOMContentLoaded', () => { maybeAutoStartTour(); });

// 若使用者剛同意隱私權聲明，緊接著自動開始導覽
(function () {
  const origAgree = window.agreeToLegal;
  if (typeof origAgree === 'function') {
    window.agreeToLegal = function () {
      origAgree.apply(this, arguments);
      maybeAutoStartTour();
    };
  }
})();

// 語言切換時，若導覽正開著，重新渲染當前步驟的文字
window.addEventListener('languageChanged', () => {
  if (document.getElementById('tour-mask')) renderTourStep(tourIdx);
});

window.startTour = startTour;
