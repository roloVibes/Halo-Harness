// What the page's address asks of the workspace (3.3.2.0 R3; 3.6.0.0 R0a): `?open=a,b` opens those panels first (a
// link, a door); `?open=all` (FULL_PAGE) opens every panel of each view, each side's drawers stacked in one drawer --
// the drivers' and the captures' door -- and a panel opened then keeps the others open.
const QUERY = typeof location === "undefined" ? "" : location.search;
export const OPEN = (/[?&]open=([\w,-]+)/.exec(QUERY)?.[1] || "").split(",").filter(Boolean);
export const FULL_PAGE = OPEN.includes("all");
