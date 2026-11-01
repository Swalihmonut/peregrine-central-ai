import { createRequire } from "module";
const require = createRequire("/Users/muhammedswaliht/khaliji-arabic-through-stories/node_modules/");
const { chromium } = require("playwright");
import fs from "fs";
import path from "path";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3005";
const SCREENSHOTS_DIR = path.resolve("reports/ux_audit_screenshots");

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

const VIEWPORTS = [
  { name: "mobile-360", width: 360, height: 800 },
  { name: "mobile-390", width: 390, height: 844 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "tablet-1024", width: 1024, height: 768 },
  { name: "desktop-1280", width: 1280, height: 800 },
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1920", width: 1920, height: 1080 },
];

const PAGES_TO_AUDIT = [
  { name: "landing", path: "/" },
  { name: "tutor", path: "/tutor" },
  { name: "speaking", path: "/speaking" },
  { name: "exams", path: "/exams" },
  { name: "notebook", path: "/notebook" },
  { name: "research", path: "/research" },
];

async function runAudit() {
  console.log(`Starting Independent UX Audit against ${BASE_URL}...`);
  const browser = await chromium.launch({ headless: true });
  const auditResults = {
    timestamp: new Date().toISOString(),
    baseUrl: BASE_URL,
    viewports: {},
    pages: {},
    contrastIssues: [],
    touchTargetIssues: [],
    mobileNavAudit: {},
    keyboardAudit: {},
    nonFunctionalControls: [],
    statesAudit: {},
  };

  const context = await browser.newContext();
  const page = await context.newPage();

  // 1. Audit Viewports & Capture Screenshots
  for (const p of PAGES_TO_AUDIT) {
    auditResults.pages[p.name] = {
      path: p.path,
      computedStyles: {},
      nonFunctionalElements: [],
    };

    console.log(`Auditing page: ${p.name} (${p.path})`);

    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto(`${BASE_URL}${p.path}`, { waitUntil: "networkidle" });

      // Save screenshot
      const ssFilename = `${p.name}_${vp.name}.png`;
      const ssPath = path.join(SCREENSHOTS_DIR, ssFilename);
      await page.screenshot({ path: ssPath, fullPage: true });

      // Extract general layout metrics
      if (vp.name === "desktop-1280") {
        const styles = await page.evaluate(() => {
          const body = document.body;
          const main = document.querySelector("main");
          const h1 = document.querySelector("h1");
          const firstBtn = document.querySelector("button, a.rounded-full");
          return {
            bodyBg: window.getComputedStyle(body).backgroundColor,
            bodyColor: window.getComputedStyle(body).color,
            mainBg: main ? window.getComputedStyle(main).backgroundColor : null,
            h1Color: h1 ? window.getComputedStyle(h1).color : null,
            btnBg: firstBtn ? window.getComputedStyle(firstBtn).backgroundColor : null,
            btnColor: firstBtn ? window.getComputedStyle(firstBtn).color : null,
          };
        });
        auditResults.pages[p.name].computedStyles = styles;
      }

      // Check Mobile Navigation at 360px & 390px
      if (vp.width <= 390 && p.name === "landing") {
        const mobileNavCheck = await page.evaluate(() => {
          const nav = document.querySelector("nav");
          const isNavHidden = nav ? window.getComputedStyle(nav).display === "none" : true;
          const hamburger = document.querySelector('button[aria-label*="menu" i], [data-testid*="hamburger" i], [data-testid*="mobile-menu" i]');
          return {
            isNavHiddenOnMobile: isNavHidden,
            hasHamburgerButton: !!hamburger,
            hamburgerVisible: hamburger ? window.getComputedStyle(hamburger).display !== "none" : false,
          };
        });
        auditResults.mobileNavAudit[vp.name] = mobileNavCheck;
      }

      // Touch Target Size Audit on Mobile (360px)
      if (vp.width === 360) {
        const touchTargets = await page.evaluate((pageName) => {
          const interactive = Array.from(document.querySelectorAll("button, a, input, select, textarea"));
          const smallTargets = [];
          for (const el of interactive) {
            const rect = el.getBoundingClientRect();
            // Visible elements only
            if (rect.width > 0 && rect.height > 0 && rect.bottom > 0) {
              const text = (el.innerText || el.getAttribute("aria-label") || el.getAttribute("data-testid") || "").trim().slice(0, 30);
              if (rect.width < 44 || rect.height < 44) {
                smallTargets.push({
                  page: pageName,
                  element: el.tagName.toLowerCase(),
                  text,
                  width: Math.round(rect.width),
                  height: Math.round(rect.height),
                  testid: el.getAttribute("data-testid") || null,
                });
              }
            }
          }
          return smallTargets;
        }, p.name);

        auditResults.touchTargetIssues.push(...touchTargets);
      }
    }

    // Inspect non-functional or disabled controls on page (at 1280px)
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE_URL}${p.path}`, { waitUntil: "networkidle" });
    const nonFunc = await page.evaluate((pageName) => {
      const items = [];
      const disabledBtns = document.querySelectorAll("button:disabled, [aria-disabled='true'], .cursor-not-allowed");
      disabledBtns.forEach((b) => {
        items.push({
          page: pageName,
          type: "disabled_button",
          text: (b.innerText || "").trim().slice(0, 40),
          testid: b.getAttribute("data-testid") || null,
        });
      });
      const deadLinks = document.querySelectorAll('a[href="#"], a[href=""]');
      deadLinks.forEach((a) => {
        items.push({
          page: pageName,
          type: "dead_link_hash",
          text: (a.innerText || "").trim().slice(0, 40),
          testid: a.getAttribute("data-testid") || null,
        });
      });
      return items;
    }, p.name);
    auditResults.nonFunctionalControls.push(...nonFunc);
  }

  // 2. Keyboard Navigation and Focus Visibility Audit
  console.log("Auditing Keyboard Navigation & Focus Rings...");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`${BASE_URL}/tutor`, { waitUntil: "networkidle" });
  
  const keyboardAudit = await page.evaluate(async () => {
    const focusable = Array.from(document.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"));
    const focusResults = [];
    for (let i = 0; i < Math.min(focusable.length, 12); i++) {
      const el = focusable[i];
      el.focus();
      const style = window.getComputedStyle(el);
      const outline = style.outlineStyle;
      const outlineWidth = style.outlineWidth;
      const boxShadow = style.boxShadow;
      const hasVisibleIndicator = (outline !== "none" && outlineWidth !== "0px") || (boxShadow !== "none" && boxShadow !== "");
      focusResults.push({
        tag: el.tagName.toLowerCase(),
        testid: el.getAttribute("data-testid"),
        text: (el.innerText || el.placeholder || "").trim().slice(0, 25),
        hasVisibleIndicator,
        outline,
        boxShadow,
      });
    }
    return focusResults;
  });
  auditResults.keyboardAudit = keyboardAudit;

  // 3. States Audit (Tutor, Speaking, Exams)
  console.log("Auditing Empty, Loading, Error, Disabled States...");
  // Tutor empty and disabled submit
  await page.goto(`${BASE_URL}/tutor`, { waitUntil: "networkidle" });
  const tutorEmptyState = await page.evaluate(() => {
    const submitBtn = document.querySelector('[data-testid="tutor-submit"]');
    const textarea = document.querySelector('[data-testid="tutor-textarea"]');
    const promptChips = document.querySelectorAll('button[class*="rounded-xl"]');
    return {
      submitDisabledWhenEmpty: submitBtn ? submitBtn.disabled : null,
      textareaValue: textarea ? textarea.value : null,
      promptChipsCount: promptChips.length,
    };
  });

  // Speaking Partner default state
  await page.goto(`${BASE_URL}/speaking`, { waitUntil: "networkidle" });
  const speakingState = await page.evaluate(() => {
    const partnerBubble = document.querySelector('[data-testid="partner-bubble"]');
    const micBtn = document.querySelector('[data-testid="mic-button"]');
    const submitBtn = document.querySelector('[data-testid="speaking-submit"]');
    return {
      initialGreetingPresent: !!partnerBubble,
      initialGreetingText: partnerBubble ? partnerBubble.innerText.slice(0, 60) : null,
      micButtonPresent: !!micBtn,
      submitButtonPresent: !!submitBtn,
    };
  });

  // Exams default state
  await page.goto(`${BASE_URL}/exams`, { waitUntil: "networkidle" });
  const examsState = await page.evaluate(() => {
    const presetInput = document.querySelector('[data-testid="exam-question-input"]');
    const analyzeBtn = document.querySelector('[data-testid="exam-analyze-btn"]');
    const options = document.querySelectorAll('[data-testid*="exam-option"]');
    return {
      presetLoaded: !!presetInput,
      presetText: presetInput ? presetInput.value || presetInput.innerText : null,
      analyzeButtonPresent: !!analyzeBtn,
      optionsCount: options.length,
    };
  });

  auditResults.statesAudit = {
    tutor: tutorEmptyState,
    speaking: speakingState,
    exams: examsState,
  };

  await browser.close();

  const reportPath = path.resolve("reports/ux_audit_probe_results.json");
  fs.writeFileSync(reportPath, JSON.stringify(auditResults, null, 2));
  console.log(`UX Audit completed. Machine-readable probe data saved to ${reportPath}`);
}

runAudit().catch((err) => {
  console.error("Audit failed:", err);
  process.exit(1);
});
