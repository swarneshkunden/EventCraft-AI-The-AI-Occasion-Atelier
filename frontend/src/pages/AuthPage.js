/**
 * Luxury Landing & Authentication Page.
 * Mood: celebration, warmth, trust, and refined luxury.
 * Includes a responsive planning preview, product sections, auth forms,
 * password visibility toggle, and instant demo launcher.
 */
import { login, signup, loadDemo } from '../services/auth.js';
import { fetchEvents } from '../services/events.js';
import { showToast } from '../utils/toast.js';
import { icons } from '../utils/icons.js';

export function renderAuthPage() {
  return `
    <div style="min-height: 100vh; background: var(--clr-bg); display: flex; flex-direction: column;">
      <header class="auth-header" data-landing-reveal>
        <div class="auth-header-brand">
          ${icons.crest(34)}
          <div>
            <div class="font-serif" style="font-size: 1.3rem; font-weight: 700; color: var(--clr-text); line-height: 1;">EventCraft AI</div>
            <div class="auth-header-tagline">THE AI OCCASION ATELIER</div>
          </div>
        </div>

        <nav class="landing-nav-links" aria-label="Main navigation">
          <a href="#landing-features">Features</a>
          <a href="#landing-how">How it works</a>
        </nav>

        <div class="auth-header-actions">
          <button id="btn-hero-demo-nav" class="btn btn-secondary btn-sm auth-header-demo">
            ${icons.sparkle(14)} Try the demo
          </button>
          <a href="#auth-card-anchor" class="btn btn-primary btn-sm">
            Sign In
          </a>
        </div>
      </header>

      <main id="main-content" tabindex="-1" class="landing-main">
        <section class="landing-hero">
          <div class="landing-hero-copy">
            <span class="landing-eyebrow" data-landing-reveal>${icons.sparkle(14)} Planning for life's meaningful moments</span>
            <h1 class="font-serif" data-landing-reveal>Make room for the moment.<br><span>We’ll help with the plan.</span></h1>
            <p data-landing-reveal>Bring your budget, timeline, guests, and vendors into one calm workspace—so you can spend less time coordinating and more time celebrating.</p>
            <div class="landing-hero-actions" data-landing-reveal>
              <a href="#auth-card-anchor" class="btn btn-gold btn-lg">Start planning</a>
              <button id="btn-hero-demo-main" class="btn btn-secondary btn-lg">
                ${icons.sparkle(18)} <span>Explore the demo</span>
              </button>
            </div>
            <div class="landing-hero-note" data-landing-reveal>For weddings, birthdays, and community celebrations</div>
          </div>

          <div class="landing-preview-wrap" data-landing-reveal>
            <div class="landing-preview-orbit" aria-hidden="true"></div>
            <div class="landing-preview" role="group" aria-label="Sample event planning dashboard">
              <div class="landing-preview-topbar">
                <span class="landing-preview-mark">${icons.crest(20)} EventCraft</span>
                <span class="landing-preview-sample">SAMPLE PLAN</span>
              </div>
              <div class="landing-preview-heading">
                <div>
                  <span class="landing-preview-kicker">UPCOMING CELEBRATION</span>
                  <h2>Priya & Arjun’s Wedding</h2>
                </div>
                <span class="landing-preview-date">${icons.timeline(13)} 68 days</span>
              </div>
              <div class="landing-preview-stats">
                <div><span>Total budget</span><strong>₹8,00,000</strong><small>Plan at a glance</small></div>
                <div><span>Guest target</span><strong>200</strong><small>Guests to welcome</small></div>
                <div><span>Next milestone</span><strong>Choose venue</strong><small>Due this week</small></div>
              </div>
              <div class="landing-preview-lower">
                <div class="landing-preview-budget">
                  <div class="landing-preview-section-title"><strong>Budget overview</strong><span>View plan</span></div>
                  <div class="landing-budget-row"><span>Venue</span><strong>₹2,40,000</strong></div>
                  <div class="landing-budget-track"><span style="width: 68%;"></span></div>
                  <div class="landing-budget-row"><span>Catering</span><strong>₹2,80,000</strong></div>
                  <div class="landing-budget-track landing-budget-track-rose"><span style="width: 54%;"></span></div>
                </div>
                <div class="landing-preview-timeline">
                  <div class="landing-preview-section-title"><strong>On your timeline</strong><span>Next steps</span></div>
                  <div class="landing-timeline-item"><i class="is-done"></i><span>Set your celebration priorities</span><small>Done</small></div>
                  <div class="landing-timeline-item"><i></i><span>Shortlist your venue</span><small>Next</small></div>
                  <div class="landing-timeline-item"><i></i><span>Meet your photographer</span><small>Upcoming</small></div>
                </div>
              </div>
            </div>
            <div class="landing-preview-caption">${icons.check(14)} A sample of your planning workspace</div>
          </div>
        </section>

        <section class="landing-proof-strip" aria-label="Planning tools">
          <div data-landing-reveal><strong>One clear budget</strong><span>Track estimates and spending</span></div>
          <div data-landing-reveal><strong>A connected timeline</strong><span>Know what comes next</span></div>
          <div data-landing-reveal><strong>Everything together</strong><span>Guests, vendors, and ideas</span></div>
        </section>

        <section id="landing-features" class="landing-section">
          <div class="landing-section-heading" data-landing-reveal>
            <span class="landing-section-kicker">YOUR CELEBRATION, IN GOOD HANDS</span>
            <h2 class="font-serif">A thoughtful plan, from first idea to final toast.</h2>
            <p>Helpful tools for the details that matter—with you in control of every decision.</p>
          </div>
          <div class="landing-feature-grid">
            <article class="landing-feature-card" data-landing-reveal>
              <div class="landing-feature-icon landing-icon-gold">${icons.budget(21)}</div>
              <h3 class="font-serif">Budget with confidence</h3>
              <p>Organize spending by category, see what remains, and compare possible changes before you commit.</p>
              <div class="landing-mini-budget" aria-hidden="true">
                <span><i></i> Venue <b>30%</b></span><span><i></i> Catering <b>35%</b></span><span><i></i> Your reserve <b>15%</b></span>
              </div>
            </article>
            <article class="landing-feature-card" data-landing-reveal>
              <div class="landing-feature-icon landing-icon-navy">${icons.timeline(21)}</div>
              <h3 class="font-serif">Keep every step in view</h3>
              <p>Build a timeline with due dates and dependencies, so the next task is clear and blockers are visible.</p>
              <div class="landing-mini-checklist" aria-hidden="true">
                <span><i class="is-done"></i> Pick an occasion date</span><span><i></i> Book a venue</span><span><i></i> Send invitations</span>
              </div>
            </article>
            <article class="landing-feature-card" data-landing-reveal>
              <div class="landing-feature-icon landing-icon-rose">${icons.vendors(21)}</div>
              <h3 class="font-serif">Bring your people together</h3>
              <p>Keep vendor notes, guest RSVPs, and planning ideas connected to the celebration they belong to.</p>
              <div class="landing-mini-people" aria-hidden="true"><span>Vendors</span><span>Guests</span><span>Ideas</span></div>
            </article>
          </div>
        </section>

        <section id="landing-how" class="landing-how">
          <div class="landing-how-intro" data-landing-reveal>
            <span class="landing-section-kicker">A SIMPLE WAY TO GET STARTED</span>
            <h2 class="font-serif">From “what if” to “we’ve got this.”</h2>
            <p>Start with what you know. Your plan can grow and change along the way.</p>
          </div>
          <div class="landing-steps">
            <article data-landing-reveal><span>01</span><div><h3>Tell us about your occasion</h3><p>Share your date, guest count, budget, and the details that make it yours.</p></div></article>
            <article data-landing-reveal><span>02</span><div><h3>Shape your planning workspace</h3><p>Organize the budget, timeline, guest list, and vendor checklist in one place.</p></div></article>
            <article data-landing-reveal><span>03</span><div><h3>Adjust as plans unfold</h3><p>Review suggestions, make your own choices, and keep your celebration on track.</p></div></article>
          </div>
        </section>

        <section class="landing-audience" data-landing-reveal>
          <div class="landing-audience-mark">${icons.crest(34)}</div>
          <div>
            <span class="landing-section-kicker">MADE FOR THE PEOPLE BEHIND THE MOMENT</span>
            <h2 class="font-serif">For couples, thoughtful hosts, and community organizers.</h2>
            <p>Whether you’re planning an intimate gathering or a full celebration, EventCraft helps keep the moving pieces in one place.</p>
          </div>
          <a href="#auth-card-anchor" class="btn btn-secondary">Meet your planning space</a>
        </section>

        <section class="landing-final-cta" data-landing-reveal>
          <span class="landing-section-kicker">YOUR NEXT CHAPTER STARTS HERE</span>
          <h2 class="font-serif">Plan the details. Be there for the moment.</h2>
          <p>Start with your occasion and build a plan at your own pace.</p>
          <a href="#auth-card-anchor" class="btn btn-gold btn-lg">Create your planning space</a>
        </section>

        <section id="auth-card-anchor" class="landing-auth-section">
          <div class="landing-auth-intro" data-landing-reveal>
            <span class="landing-section-kicker">WELCOME TO EVENTCRAFT</span>
            <h2 class="font-serif">Your celebration starts with a plan.</h2>
          </div>
          <div class="landing-auth-layout">
            <div class="card landing-demo-card" data-landing-reveal>
              <div class="landing-demo-icon">${icons.sparkle(21)}</div>
              <div>
                <span class="landing-section-kicker">TAKE A LOOK AROUND</span>
                <h3 class="font-serif">Explore a sample celebration</h3>
                <p class="text-muted">Open a sample event and see how the budget, tasks, guests, vendors, and ideas fit together.</p>
                <button id="btn-quick-demo" class="btn btn-gold">
                  ${icons.sparkle(16)} <span>Try the demo</span>
                </button>
              </div>
            </div>

            <div class="card landing-auth-card" data-landing-reveal>
              <div class="landing-auth-tabs">
                <button id="tab-login" class="btn btn-ghost landing-auth-tab is-active">Sign In</button>
                <button id="tab-signup" class="btn btn-ghost landing-auth-tab">Create Account</button>
              </div>
              <div id="auth-rate-limit-banner" class="landing-rate-limit" style="display: none;">
                ${icons.alertCircle(16)} <span id="rate-limit-text">Too many attempts. Please slow down.</span>
              </div>
              <form id="form-login" class="form-group landing-auth-form">
                <div class="form-group">
                  <label for="login-email">Email Address <span class="required">*</span></label>
                  <input type="email" id="login-email" required placeholder="host@eventcraft.ai" autocomplete="email" />
                </div>
                <div class="form-group">
                  <label for="login-password">Password <span class="required">*</span></label>
                  <div class="password-wrapper">
                    <input type="password" id="login-password" required placeholder="••••••••" autocomplete="current-password" />
                    <button type="button" class="password-toggle-btn" data-target="login-password" aria-label="Toggle password visibility">${icons.eye(16)}</button>
                  </div>
                </div>
                <button type="submit" id="btn-submit-login" class="btn btn-primary">Sign In to Workspace</button>
              </form>
              <form id="form-signup" class="form-group landing-auth-form" style="display: none;">
                <div class="form-group">
                  <label for="signup-name">Your Full Name <span class="required">*</span></label>
                  <input type="text" id="signup-name" required placeholder="e.g. Alex & Jordan" />
                </div>
                <div class="form-group">
                  <label for="signup-email">Email Address <span class="required">*</span></label>
                  <input type="email" id="signup-email" required placeholder="you@domain.com" autocomplete="email" />
                </div>
                <div class="form-group">
                  <label for="signup-password">Password <span class="required">*</span></label>
                  <div class="password-wrapper">
                    <input type="password" id="signup-password" minlength="8" maxlength="128" pattern="(?=.*[A-Z])(?=.*[0-9]).{8,128}" title="Use at least 8 characters, including one uppercase letter and one number." aria-describedby="signup-password-hint" required placeholder="••••••••" autocomplete="new-password" />
                    <button type="button" class="password-toggle-btn" data-target="signup-password" aria-label="Toggle password visibility">${icons.eye(16)}</button>
                  </div>
                  <small id="signup-password-hint" class="auth-password-hint" role="note"><strong>Important:</strong> Password must include 8–128 characters, including at least one uppercase letter and one number.</small>
                </div>
                <div class="form-group">
                  <label for="signup-currency">Base Currency</label>
                  <select id="signup-currency">
                    <option value="INR" selected>INR (₹) — Indian Rupee</option>
                    <option value="USD">USD ($) — US Dollar</option>
                    <option value="EUR">EUR (€) — Euro</option>
                    <option value="GBP">GBP (£) — British Pound</option>
                    <option value="CAD">CAD (CA$) — Canadian Dollar</option>
                    <option value="AUD">AUD (AU$) — Australian Dollar</option>
                  </select>
                </div>
                <button type="submit" id="btn-submit-signup" class="btn btn-gold">Create Free Atelier Account</button>
              </form>
            </div>
          </div>
        </section>
      </main>

      <footer class="landing-footer" data-landing-reveal>
        <div class="auth-header-brand">
          ${icons.crest(25)}
          <div><strong>EventCraft AI</strong><span>THE AI OCCASION ATELIER</span></div>
        </div>
        <p>Plan with care. Celebrate with presence.</p>
      </footer>

    </div>
  `;
}

export function initAuthPageEvents() {
  initLandingMotion();

  const tabLogin = document.getElementById('tab-login');
  const tabSignup = document.getElementById('tab-signup');
  const formLogin = document.getElementById('form-login');
  const formSignup = document.getElementById('form-signup');

  tabLogin?.addEventListener('click', () => {
    tabLogin.classList.add('is-active');
    tabSignup.classList.remove('is-active');

    formLogin.style.display = 'flex';
    formSignup.style.display = 'none';
  });

  tabSignup?.addEventListener('click', () => {
    tabSignup.classList.add('is-active');
    tabLogin.classList.remove('is-active');

    formSignup.style.display = 'flex';
    formLogin.style.display = 'none';
  });

  // Password visibility toggle buttons
  document.querySelectorAll('.password-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (!input) return;
      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';
      btn.innerHTML = isPassword ? icons.eyeOff(16) : icons.eye(16);
    });
  });

  // Demo buttons
  const triggerDemo = async (btn) => {
    btn.disabled = true;
    const oldText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Loading sample wedding...';
    try {
      await loadDemo();
      await fetchEvents();
      showToast('Sample wedding loaded. Welcome!', 'success');
      window.location.hash = '#dashboard';
    } catch (err) {
      showToast(err.message || 'Demo initialization failed', 'error');
      btn.disabled = false;
      btn.innerHTML = oldText;
    }
  };

  document.getElementById('btn-quick-demo')?.addEventListener('click', function () {
    triggerDemo(this);
  });
  document.getElementById('btn-hero-demo-main')?.addEventListener('click', function () {
    triggerDemo(this);
  });
  document.getElementById('btn-hero-demo-nav')?.addEventListener('click', function () {
    triggerDemo(this);
  });

  // Login Submit
  formLogin?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const btn = document.getElementById('btn-submit-login');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Authenticating...';

    try {
      await login(email, password);
      await fetchEvents();
      showToast('Welcome back to EventCraft!', 'success');
      window.location.hash = '#dashboard';
    } catch (err) {
      if (err.status === 429) {
        showRateLimitCountdown(err.retryAfter || 300);
      } else {
        showToast(err.message || 'Invalid email or password', 'error');
      }
      btn.disabled = false;
      btn.textContent = 'Sign In to Workspace';
    }
  });

  // Signup Submit
  formSignup?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('signup-name').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = document.getElementById('signup-password').value;
    const currency = document.getElementById('signup-currency').value;
    const btn = document.getElementById('btn-submit-signup');

    if (password.length < 8 || password.length > 128 || !/[A-Z]/.test(password) || !/[0-9]/.test(password)) {
      showToast('Password must be 8-128 characters and include at least one uppercase letter and one number.', 'error');
      document.getElementById('signup-password').focus();
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Setting up atelier...';

    try {
      await signup(email, password, name, currency);
      document.getElementById('login-email').value = email;
      tabLogin?.click();
      showToast('If the address was available, the account was created. Sign in to continue.', 'info');
      btn.disabled = false;
      btn.textContent = 'Create Free Atelier Account';
    } catch (err) {
      if (err.status === 429) {
        showRateLimitCountdown(err.retryAfter || 300);
      } else {
        showToast(err.message || 'Signup failed', 'error');
      }
      btn.disabled = false;
      btn.textContent = 'Create Free Atelier Account';
    }
  });
}

function initLandingMotion() {
  const targets = document.querySelectorAll('[data-landing-reveal]');
  if (
    !targets.length
    || !('IntersectionObserver' in window)
    || window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) {
    return;
  }

  document.documentElement.classList.add('landing-motion-ready');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
      } else if (!entry.target.contains(document.activeElement)) {
        entry.target.classList.remove('is-visible');
      }
    });
  }, { threshold: 0.14, rootMargin: '0px 0px -32px 0px' });

  targets.forEach((target) => {
    observer.observe(target);
    target.addEventListener('focusin', () => {
      target.classList.add('is-visible');
    });
    target.addEventListener('focusout', () => {
      requestAnimationFrame(() => {
        const bounds = target.getBoundingClientRect();
        const isInViewport = bounds.bottom > 0 && bounds.top < window.innerHeight;
        if (!target.contains(document.activeElement) && !isInViewport) {
          target.classList.remove('is-visible');
        }
      });
    });
  });
}

function showRateLimitCountdown(seconds) {
  const banner = document.getElementById('auth-rate-limit-banner');
  const text = document.getElementById('rate-limit-text');
  if (!banner || !text) return;

  banner.style.display = 'flex';
  let remaining = seconds;
  text.textContent = `Security limit: please wait ${remaining}s before trying again.`;

  const timer = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(timer);
      banner.style.display = 'none';
    } else {
      text.textContent = `Security limit: please wait ${remaining}s before trying again.`;
    }
  }, 1000);
}
