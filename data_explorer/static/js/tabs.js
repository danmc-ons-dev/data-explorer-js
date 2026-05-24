const ROUTE_TAB_CONFIG = {
  "/framework": {
    subtabMap: {
      0: "soschi",
      1: "heat-and-cold",
      2: "extreme-weather-events",
      3: "air-pollution-and-air-borne-diseases",
      4: "waterborne-diseases",
      5: "vectorborne-diseases",
      6: "undernutrition",
      7: "mental-health",
      8: "chemical-contaminants",
      9: "healthcare-systems-and-facilities",
    },
    defaultInnerTabs: {
      "extreme-weather-events": "wildfires-tab",
      "air-pollution-and-air-borne-diseases": "air-pollution-tab",
    },
  },
  "/indicator_calculators": {
    subtabMap: {
      0: "descriptive-statistics",
      1: "heat-and-cold",
      2: "extreme-weather-events",
      4: "waterborne-diseases",
      5: "vectorborne-diseases",
      7: "mental-health",
    },
    defaultInnerTabs: {
      "descriptive-statistics": "DescStatsSelectFileTab",
      "heat-and-cold": "defaultOpen",
      "extreme-weather-events": "wildfires-select-file",
      "waterborne-diseases": "WaterborneSelectFileTab",
      "vectorborne-diseases": "vector-borne-select-file",
      "mental-health": "mental-health-select-file",
    },
  },
};

function normalizePath(pathname) {
  if (!pathname) {
    return "/";
  }
  return pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
}

function getCurrentTabConfig() {
  const routePath = normalizePath(window.location.pathname);
  return ROUTE_TAB_CONFIG[routePath] || { subtabMap: {}, defaultInnerTabs: {} };
}

function safeURL(href) {
  if (!href) {
    return null;
  }
  try {
    return new URL(href, window.location.href);
  } catch (error) {
    return null;
  }
}

function isSamePage(url) {
  if (!url) {
    return false;
  }
  const current = new URL(window.location.href);
  return (
    url.origin === current.origin &&
    normalizePath(url.pathname) === normalizePath(current.pathname)
  );
}

function findSubtabLinkByHash(hash) {
  if (!hash) {
    return null;
  }
  const target = document.querySelector(hash);
  if (!target || !target.classList.contains("subtab-content")) {
    return null;
  }
  let match = null;
  document.querySelectorAll(".subtab").forEach((link) => {
    const url = safeURL(link.getAttribute("href"));
    if (!url || !isSamePage(url)) {
      return;
    }
    if (url.hash === hash) {
      match = link;
    }
  });
  return match;
}

function findSubtabLinkByHashAny(hash) {
  if (!hash) {
    return null;
  }
  let match = null;
  document.querySelectorAll(".subtab").forEach((link) => {
    const url = safeURL(link.getAttribute("href"));
    if (!url || !isSamePage(url)) {
      return;
    }
    if (url.hash === hash) {
      match = link;
    }
  });
  return match;
}

function activateOnsTabByHash(hash) {
  const link = document.querySelector('.ons-tab[href="' + hash + '"]');
  if (!link) {
    return false;
  }
  const panel = document.querySelector(hash);
  if (!panel || !panel.classList.contains("ons-tabs__panel")) {
    return false;
  }

  const tabsRoot = link.closest(".ons-tabs") || document;
  tabsRoot.querySelectorAll(".ons-tabs__panel").forEach((tabPanel) => {
    tabPanel.classList.add("ons-tabs__panel--hidden");
    tabPanel.setAttribute("aria-hidden", "true");
  });

  panel.classList.remove("ons-tabs__panel--hidden");
  panel.setAttribute("aria-hidden", "false");

  tabsRoot.querySelectorAll(".ons-tab").forEach((tabLink) => {
    tabLink.setAttribute("aria-selected", "false");
    tabLink.setAttribute("tabindex", "-1");
    const item = tabLink.closest(".ons-tab__list-item");
    if (item) {
      item.classList.remove("ons-tab__list-item--active");
    }
  });

  link.setAttribute("aria-selected", "true");
  link.setAttribute("tabindex", "0");
  const activeItem = link.closest(".ons-tab__list-item");
  if (activeItem) {
    activeItem.classList.add("ons-tab__list-item--active");
  }

  return true;
}

function closeHeaderNavMenu() {
  const toggleButton = document.querySelector(".ons-js-toggle-nav-menu");
  const navMenu = document.querySelector(".ons-js-nav-menu");
  if (!toggleButton || !navMenu) {
    return;
  }

  const isExpanded = toggleButton.getAttribute("aria-expanded") === "true";
  const isHidden = navMenu.classList.contains("ons-u-d-no");
  if (!isExpanded && isHidden) {
    return;
  }

  // Move focus out of the menu before hiding it from assistive tech.
  if (navMenu.contains(document.activeElement)) {
    toggleButton.focus({ preventScroll: true });
  }

  toggleButton.classList.remove("active");
  toggleButton.setAttribute("aria-expanded", "false");
  navMenu.classList.add("ons-u-d-no");
  navMenu.setAttribute("aria-hidden", "true");
}

function normalizeHashValue(rawHash) {
  return String(rawHash || "").replace(/^#/, "").trim().toLowerCase();
}

function getDefaultAllowedSubtabHash() {
  if (!Array.isArray(window.allowedFrameworkHashes)) {
    return null;
  }

  for (const rawHash of window.allowedFrameworkHashes) {
    const hash = normalizeHashValue(rawHash);
    if (!hash) {
      continue;
    }
    const target = document.getElementById(hash);
    if (target && target.classList.contains("subtab-content")) {
      return "#" + hash;
    }
  }

  return null;
}

function enforceAllowedFrameworkHash(rawHash) {
  if (window.enforceHashAllowlist === false) {
    return false;
  }

  if (!Array.isArray(window.allowedFrameworkHashes)) {
    return false;
  }

  const normalizedAllowedHashes = new Set(
    window.allowedFrameworkHashes
      .map((hash) => normalizeHashValue(hash))
      .filter((hash) => hash)
  );

  // No restrictions configured.
  if (normalizedAllowedHashes.size === 0) {
    return false;
  }

  const currentHash = normalizeHashValue(rawHash);
  if (!currentHash) {
    return false;
  }

  if (normalizedAllowedHashes.has(currentHash)) {
    return false;
  }

  // Allow inner tab hashes when their parent subtab section is allowed.
  const hashTarget = document.getElementById(currentHash);
  if (hashTarget) {
    const parentSubtab = hashTarget.closest(".subtab-content");
    if (parentSubtab && normalizedAllowedHashes.has(normalizeHashValue(parentSubtab.id))) {
      return false;
    }
  }

  const redirectTarget = window.comingSoonUrl || "/coming_soon";
  window.location.assign(redirectTarget);
  return true;
}

document.addEventListener("DOMContentLoaded", function () {

  const currentURL = window.location.href;
  const tabs = document.querySelectorAll(".tab");

  tabs.forEach((tab) => {
    tab.classList.remove("active-tab");
    if (tab.getAttribute("href") === currentURL || tab.href === currentURL) {
      tab.classList.add("active-tab");
    }
  });

  document.querySelectorAll(".subtab").forEach((tab) => {
    tab.addEventListener("click", function (e) {
      const url = safeURL(this.getAttribute("href"));
      if (!url || !isSamePage(url) || !url.hash) {
        return;
      }

      e.preventDefault();
      if (enforceAllowedFrameworkHash(url.hash)) {
        closeHeaderNavMenu();
        return;
      }
      history.replaceState(null, "", url.hash);
      activateTabFromHash();
      closeHeaderNavMenu();
    });
  });

  document.addEventListener("click", function (e) {
    const link = e.target.closest("a");
    if (!link || !link.closest(".ons-header, .ons-footer")) {
      return;
    }
    const url = safeURL(link.getAttribute("href"));
    if (!url || !url.hash) {
      return;
    }
    const current = new URL(window.location.href);
    if (url.origin !== current.origin) {
      return;
    }
    const currentPath = normalizePath(current.pathname);
    const targetPath = normalizePath(url.pathname);
    if (currentPath === targetPath) {
      return;
    }
    sessionStorage.setItem("pendingHash", url.hash);
    sessionStorage.setItem("pendingPath", targetPath);
    e.preventDefault();
    window.location.assign(url.pathname + url.search);
  });
});

function setTabNo(tabno) {
  sessionStorage.setItem("tabno", tabno);
};

function setInnerTabId(innerTabId) {
  sessionStorage.setItem("innerTabId", innerTabId);
};

function activateTabFromHashValue(hash) {
  if (!hash) {
    return false;
  }
  const currentTabConfig = getCurrentTabConfig();

  var subtabLink = findSubtabLinkByHash(hash);
  if (subtabLink) {
    document.querySelectorAll(".subtab").forEach((innerTab) => {
      innerTab.classList.remove("active-tab");
    });

    document.querySelectorAll(".subtab-content").forEach((content) => {
      content.classList.remove("active-content");
    });

    subtabLink.classList.add("active-tab");
    const content = document.querySelector(hash);
    if (content) {
      content.classList.add("active-content");
      const defaultInnerTabId = currentTabConfig.defaultInnerTabs[content.id];
      if (defaultInnerTabId) {
        const defaultInnerTab =
          document.querySelector('.ons-tab[href="#' + defaultInnerTabId + '"]') ||
          document.getElementById(defaultInnerTabId);
        if (defaultInnerTab) {
          defaultInnerTab.click();
        }
      }
    }
    return true;
  }

  var innerTabLink = document.querySelector('.ons-tab[href="' + hash + '"]');
  if (innerTabLink) {
    const onsTabHandled = activateOnsTabByHash(hash);
    var parentContent = innerTabLink.closest(".subtab-content");
    if (parentContent && parentContent.id) {
      document.querySelectorAll(".subtab").forEach((innerTab) => {
        innerTab.classList.remove("active-tab");
      });

      document.querySelectorAll(".subtab-content").forEach((content) => {
        content.classList.remove("active-content");
      });

      const content = document.getElementById(parentContent.id);
      if (content) {
        content.classList.add("active-content");
      }

      var parentSubtabLink = findSubtabLinkByHash("#" + parentContent.id);
      if (parentSubtabLink) {
        parentSubtabLink.classList.add("active-tab");
      } else {
        const directSubtabLink = findSubtabLinkByHashAny(hash);
        if (directSubtabLink) {
          directSubtabLink.classList.add("active-tab");
        }
      }
    }
    if (!onsTabHandled) {
      innerTabLink.click();
    }
    return true;
  }

  return false;
}

function activateTabFromHash() {
  return activateTabFromHashValue(window.location.hash);
}

window.addEventListener('load', function () {
  if (!window.location.hash) {
    const defaultAllowedHash = getDefaultAllowedSubtabHash();
    if (defaultAllowedHash) {
      history.replaceState(null, "", defaultAllowedHash);
    }
  }

  if (enforceAllowedFrameworkHash(window.location.hash)) {
    return;
  }

  var pendingHash = sessionStorage.getItem("pendingHash");
  if (pendingHash) {
    if (enforceAllowedFrameworkHash(pendingHash)) {
      return;
    }

    const pendingPath = sessionStorage.getItem("pendingPath");
    const currentPath = normalizePath(window.location.pathname);
    sessionStorage.removeItem("pendingHash");
    sessionStorage.removeItem("pendingPath");
    if (!pendingPath || pendingPath === currentPath) {
      activateTabFromHashValue(pendingHash);
      history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search + pendingHash
      );
      return;
    }
  }

  var innerTabId = sessionStorage.getItem("innerTabId");
  if (innerTabId) {
    history.replaceState(null, "", "#" + innerTabId);
    activateTabFromHash();
    sessionStorage.removeItem("innerTabId");
    return;
  }

  var handledHash = activateTabFromHash();

  if (handledHash) {
    return;
  }

  var tabno = sessionStorage.getItem("tabno");
  if (tabno !== null) {
    const subtabId = getCurrentTabConfig().subtabMap[tabno];
    if (subtabId) {
      history.replaceState(null, "", "#" + subtabId);
      activateTabFromHash();
    }
    sessionStorage.removeItem("tabno");
  }

  // If no content is visible, activate the tab that has active-tab, or fall back to first tab
  if (!document.querySelector(".subtab-content.active-content")) {
    const activeTab = document.querySelector(".subtab.active-tab") || document.querySelector(".subtab");
    if (activeTab) {
      const href = activeTab.getAttribute("href");
      if (href && href.startsWith("#")) {
        history.replaceState(null, "", href);
        activateTabFromHash();
      }
    }
  }
});

window.addEventListener('hashchange', function () {
  if (enforceAllowedFrameworkHash(window.location.hash)) {
    return;
  }
  activateTabFromHash();
});

function openInnerTab(evt, tabName) {
  // Declare all variables
  var i, tabcontent, tablinks;

  // Get all elements with class="innertab-content" and hide them
  tabcontent = document.getElementsByClassName("innertab-content");
  for (i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }

  // Get all elements with class="inntertab" and remove the class "active"
  tablinks = document.getElementsByClassName("active-innertab");
  for (i = 0; i < tablinks.length; i++) {
    tablinks[i].className = tablinks[i].className.replace(" active-innertab", "");
  }

  // Show the current tab, and add an "active" class to the button that opened the tab
  document.getElementById(tabName).style.display = "block";
  evt.currentTarget.className += " active-innertab";
};

function gotoInnerTab(tabNo, tabName){
  setTabNo(tabNo);
  setInnerTabId(tabName);
  var innerTabLink = document.querySelector('.ons-tab[href="#' + tabName + '"]');
  if (innerTabLink) {
    innerTabLink.click();
    return;
  }
  var fallbackTab = document.getElementById(tabName);
  if (fallbackTab) {
    fallbackTab.click();
  }
};

function resizeTooltips() {
  function adjustTooltips() {
    var tooltips = document.querySelectorAll('.tooltiptext');
    tooltips.forEach(function(tooltip) {
      var ggparentWidth = tooltip.parentElement.parentElement.parentElement.offsetWidth;
      var parentWidth = tooltip.parentElement.parentElement.offsetWidth;
      tooltip.style.width = ggparentWidth + 'px';
      tooltip.style.marginLeft = "-" + parentWidth + 'px';
    });
  }

  window.onload = function() {
    setTimeout(adjustTooltips, 100); // Adjust tooltips after a short delay

    var observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length) {
          setTimeout(adjustTooltips, 100); // Adjust tooltips after nodes are added
        }
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Assuming you have a way to detect tab changes, e.g., a class 'tab' on tab buttons
    var tabs = document.querySelectorAll('.tab');
    tabs.forEach(function(tab) {
      tab.addEventListener('click', function() {
        setTimeout(adjustTooltips, 100); // Adjust tooltips after tab change
      });
    });
  };
}
