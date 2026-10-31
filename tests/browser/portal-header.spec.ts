import { expect, test } from "@playwright/test";

test("portal header distinguishes direct links from dropdown parent menus", async ({ page }) => {
  const period = "from_date=2026-07-01&to_date=2027-06-30";
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/?${period}`);
  const header = page.locator(".portal-header");
  const desktopNavigation = header.getByRole("navigation", { name: "Primary navigation", exact: true });

  await expect(header.getByAltText("Vardhaman College of Engineering logo")).toHaveCount(0);
  await expect(header.getByText("Faculty Research & Development Portal – EEE", { exact: true })).toBeVisible();
  await expect(header.getByText("Vardhaman College of Engineering", { exact: true })).toHaveCount(0);
  await expect(desktopNavigation.getByRole("link", { name: "Overview", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(header).toHaveCSS("border-bottom-style", "solid");
  expect((await header.boundingBox())?.height).toBeLessThanOrEqual(70);
  await expect(page.locator(".portal-navigation-desktop .portal-nav-link").first()).toHaveCSS("background-color", "rgb(70, 85, 143)");
  await expect(page.locator(".portal-navigation-desktop .portal-chevron")).toHaveCount(3);
  await expect(page.locator(".portal-navigation-desktop .portal-nav-link .portal-chevron")).toHaveCount(0);
  await desktopNavigation.getByRole("link", { name: "Publications", exact: true }).hover();
  await expect(desktopNavigation.getByRole("link", { name: "Publications", exact: true })).toHaveCSS("background-color", "rgb(238, 241, 249)");

  const facultyDevelopment = desktopNavigation.getByRole("button", { name: "Faculty Development", exact: true });
  const researchFunding = desktopNavigation.getByRole("button", { name: "Research Funding", exact: true });
  const reports = desktopNavigation.getByRole("button", { name: "Reports", exact: true });
  await facultyDevelopment.click();
  await expect(facultyDevelopment).toHaveAttribute("aria-expanded", "true");
  await expect(facultyDevelopment).toHaveClass(/open/);
  await expect(desktopNavigation.getByRole("menuitem", { name: /FDP \/ STTP/ })).toHaveAttribute("href", `/fdp?${period}`);
  await researchFunding.click();
  await expect(facultyDevelopment).toHaveAttribute("aria-expanded", "false");
  await expect(researchFunding).toHaveAttribute("aria-expanded", "true");
  await expect(desktopNavigation.getByRole("menuitem", { name: "Sponsored Research" })).toHaveAttribute("href", `/research-projects?${period}`);
  await expect(desktopNavigation.getByRole("menuitem", { name: "Consultancy" })).toHaveAttribute("href", `/consultancy?${period}`);
  await expect(desktopNavigation.getByRole("menuitem", { name: "Seed Money / Internal Grants" })).toHaveAttribute("href", `/seed-money?${period}`);
  await expect(desktopNavigation.getByRole("menuitem", { name: "NBA Funding Reports" })).toHaveCount(0);

  await reports.click();
  await expect(reports).toHaveAttribute("aria-expanded", "true");
  await expect(desktopNavigation.getByRole("menuitem", { name: "NBA Funding Reports" })).toHaveAttribute("href", `/nba-reports?${period}`);
  await page.keyboard.press("Escape");
  await expect(reports).toHaveAttribute("aria-expanded", "false");
  await expect(desktopNavigation.getByRole("menuitem", { name: "NBA Funding Reports" })).toHaveCount(0);

  await researchFunding.click();
  await page.locator("main").click({ position: { x: 8, y: 8 } });
  await expect(researchFunding).toHaveAttribute("aria-expanded", "false");

  await page.goto(`/fdp?${period}`);
  await expect(desktopNavigation.getByRole("button", { name: "Faculty Development", exact: true })).toHaveClass(/active-parent/);

  await page.setViewportSize({ width: 1000, height: 900 });
  await page.goto(`/consultancy?${period}`);
  const compactNavigation = header.getByRole("navigation", { name: "Condensed primary navigation", exact: true });
  const more = compactNavigation.getByRole("button", { name: "More", exact: true });
  await expect(more).toHaveAttribute("aria-expanded", "false");
  await expect(more).toHaveClass(/active-parent/);
  await more.click();
  await expect(compactNavigation.getByRole("menuitem", { name: "Consultancy" })).toHaveAttribute("href", `/consultancy?${period}`);
  await expect(compactNavigation.getByRole("menuitem", { name: "NBA Funding Reports" })).toBeVisible();

  await page.setViewportSize({ width: 600, height: 900 });
  await page.goto(`/?${period}`);
  await header.getByRole("button", { name: "Menu", exact: true }).click();
  const mobileNavigation = header.getByRole("navigation", { name: "Mobile primary navigation", exact: true });
  await mobileNavigation.getByRole("button", { name: "Faculty Development", exact: true }).click();
  await expect(mobileNavigation.getByRole("link", { name: "Certifications & MOOCs", exact: true })).toHaveAttribute("href", `/certifications?${period}`);
  await expect(mobileNavigation.locator(".portal-chevron")).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
