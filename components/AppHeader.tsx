"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useDateRange } from "@/components/DateRange";

type NavLink = {
  label: string;
  href: string;
};

type NavigationItem = NavLink & {
  children?: NavLink[];
};

const navigation: NavigationItem[] = [
  { label: "Overview", href: "/" },
  { label: "Publications", href: "/publications" },
  { label: "Patents", href: "/patents" },
  { label: "Books & Chapters", href: "/books" },
  {
    label: "Faculty Development",
    href: "/fdp",
    children: [
      { label: "FDP / STTP / Workshops / Webinars / Seminars / Internships / Industrial Training", href: "/fdp" },
      { label: "Certifications & MOOCs", href: "/certifications" },
    ],
  },
  {
    label: "Research Funding",
    href: "/research-projects",
    children: [
      { label: "Sponsored Research", href: "/research-projects" },
      { label: "Consultancy", href: "/consultancy" },
      { label: "Seed Money / Internal Grants", href: "/seed-money" },
    ],
  },
  {
    label: "Reports",
    href: "/nba-reports",
    children: [{ label: "NBA Funding Reports", href: "/nba-reports" }],
  },
  { label: "Masters", href: "/masters" },
];

const compactNavigation = navigation.slice(0, 4);
const overflowNavigation = navigation.slice(4);

function matchesRoute(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function itemIsActive(pathname: string, item: NavigationItem) {
  return matchesRoute(pathname, item.href) || item.children?.some((child) => matchesRoute(pathname, child.href)) || false;
}

export default function AppHeader() {
  const pathname = usePathname();
  const { range } = useDateRange();
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileSection, setMobileSection] = useState<string | null>(null);
  const headerRef = useRef<HTMLElement>(null);
  const rangeQuery = new URLSearchParams(range).toString();

  useEffect(() => {
    function closeFromOutside(event: PointerEvent) {
      if (headerRef.current && !headerRef.current.contains(event.target as Node)) {
        setOpenMenu(null);
        setMobileOpen(false);
      }
    }

    function closeFromEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenMenu(null);
        setMobileOpen(false);
        setMobileSection(null);
      }
    }

    document.addEventListener("pointerdown", closeFromOutside);
    document.addEventListener("keydown", closeFromEscape);
    return () => {
      document.removeEventListener("pointerdown", closeFromOutside);
      document.removeEventListener("keydown", closeFromEscape);
    };
  }, []);

  function hrefWithRange(href: string) {
    return rangeQuery ? `${href}?${rangeQuery}` : href;
  }

  function closeMenus() {
    setOpenMenu(null);
    setMobileOpen(false);
    setMobileSection(null);
  }

  const overflowIsActive = overflowNavigation.some((item) => itemIsActive(pathname, item));

  function desktopDropdown(item: NavigationItem, menuId: string) {
    const active = itemIsActive(pathname, item);
    const isOpen = openMenu === menuId;

    return (
      <div className="portal-nav-menu" key={item.label}>
        <button
          aria-controls={menuId}
          aria-expanded={isOpen}
          aria-haspopup="menu"
          className={`portal-nav-trigger${active ? " active-parent" : ""}${isOpen ? " open" : ""}`}
          onClick={() => setOpenMenu(isOpen ? null : menuId)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") setOpenMenu(menuId);
          }}
          type="button"
        >
          {item.label}
          <span aria-hidden="true" className="portal-chevron" />
        </button>
        {isOpen && (
          <div className="portal-dropdown" id={menuId} role="menu">
            {item.children?.map((child) => (
              <Link
                aria-current={matchesRoute(pathname, child.href) ? "page" : undefined}
                className={matchesRoute(pathname, child.href) ? "active" : undefined}
                href={hrefWithRange(child.href)}
                key={child.href}
                onClick={closeMenus}
                role="menuitem"
              >
                {child.label}
              </Link>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <header className="portal-header" ref={headerRef}>
      <div className="portal-header-shell">
        <Link href={hrefWithRange("/")} className="portal-brand" onClick={closeMenus}>
          <span className="portal-title">Faculty Research &amp; Development Portal – EEE</span>
        </Link>

        <nav className="portal-navigation portal-navigation-desktop" aria-label="Primary navigation">
          {navigation.map((item) => {
              const active = itemIsActive(pathname, item);
              if (!item.children) {
                return (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={`portal-nav-link${active ? " active" : ""}`}
                    href={hrefWithRange(item.href)}
                    key={item.label}
                    onClick={closeMenus}
                  >
                    {item.label}
                  </Link>
                );
              }
              return desktopDropdown(item, `desktop-menu-${item.label.replaceAll(" ", "-").toLowerCase()}`);
          })}
        </nav>

        <nav className="portal-navigation portal-navigation-compact" aria-label="Condensed primary navigation">
          {compactNavigation.map((item) => (
            <Link
              aria-current={itemIsActive(pathname, item) ? "page" : undefined}
              className={`portal-nav-link${itemIsActive(pathname, item) ? " active" : ""}`}
              href={hrefWithRange(item.href)}
              key={item.label}
              onClick={closeMenus}
            >
              {item.label}
            </Link>
          ))}
          <div className="portal-nav-menu">
            <button
              aria-controls="desktop-menu-more"
              aria-expanded={openMenu === "desktop-menu-more"}
              aria-haspopup="menu"
              className={`portal-nav-trigger${overflowIsActive ? " active-parent" : ""}${openMenu === "desktop-menu-more" ? " open" : ""}`}
              onClick={() => setOpenMenu(openMenu === "desktop-menu-more" ? null : "desktop-menu-more")}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") setOpenMenu("desktop-menu-more");
              }}
              type="button"
            >
              More
            </button>
            {openMenu === "desktop-menu-more" && (
              <div className="portal-dropdown portal-overflow-dropdown" id="desktop-menu-more" role="menu">
                {overflowNavigation.map((item) => item.children ? (
                  <section className="portal-overflow-group" key={item.label}>
                    <span>{item.label}</span>
                    {item.children.map((child) => (
                      <Link
                        aria-current={matchesRoute(pathname, child.href) ? "page" : undefined}
                        className={matchesRoute(pathname, child.href) ? "active" : undefined}
                        href={hrefWithRange(child.href)}
                        key={child.href}
                        onClick={closeMenus}
                        role="menuitem"
                      >
                        {child.label}
                      </Link>
                    ))}
                  </section>
                ) : (
                  <Link
                    aria-current={itemIsActive(pathname, item) ? "page" : undefined}
                    className={itemIsActive(pathname, item) ? "active" : undefined}
                    href={hrefWithRange(item.href)}
                    key={item.href}
                    onClick={closeMenus}
                    role="menuitem"
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </nav>

        <button
          aria-controls="mobile-primary-navigation"
          aria-expanded={mobileOpen}
          className="portal-mobile-toggle"
          onClick={() => setMobileOpen((open) => !open)}
          type="button"
        >
          <span aria-hidden="true">☰</span>
          Menu
        </button>
      </div>

      {mobileOpen && (
        <nav className="portal-navigation portal-navigation-mobile" id="mobile-primary-navigation" aria-label="Mobile primary navigation">
            {navigation.map((item) => {
              const active = itemIsActive(pathname, item);
              if (!item.children) {
                return (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={`portal-mobile-link${active ? " active" : ""}`}
                    href={hrefWithRange(item.href)}
                    key={item.label}
                    onClick={closeMenus}
                  >
                    {item.label}
                  </Link>
                );
              }

              const expanded = mobileSection === item.label;
              return (
                <section className="portal-mobile-section" key={item.label}>
                  <button
                    aria-controls={`mobile-menu-${item.label.replaceAll(" ", "-").toLowerCase()}`}
                    aria-expanded={expanded}
                    className={`portal-mobile-section-trigger${active ? " active" : ""}${expanded ? " open" : ""}`}
                    onClick={() => setMobileSection(expanded ? null : item.label)}
                    type="button"
                  >
                    {item.label}
                    <span aria-hidden="true" className="portal-chevron" />
                  </button>
                  {expanded && (
                    <div id={`mobile-menu-${item.label.replaceAll(" ", "-").toLowerCase()}`} className="portal-mobile-children">
                      {item.children.map((child) => (
                        <Link
                          aria-current={matchesRoute(pathname, child.href) ? "page" : undefined}
                          className={matchesRoute(pathname, child.href) ? "active" : undefined}
                          href={hrefWithRange(child.href)}
                          key={child.href}
                          onClick={closeMenus}
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </section>
              );
            })}
        </nav>
      )}
    </header>
  );
}
