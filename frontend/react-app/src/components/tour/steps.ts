export type TourSpot = "navbar" | "dock" | "chat" | "composer" | "messages" | "brand" | "cat" | null;
export type TourMenu = "db" | "sql" | "chats" | "schema" | null;

export interface TourStep {
  id: string;
  title: string;
  body: string;
  /** Region to spotlight (rest of the screen goes dark). */
  spot: TourSpot;
  /** Dock menu to auto-open for this step. */
  openMenu: TourMenu;
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    title: "Welcome to DIDA",
    body: "DIDA turns plain-English questions into SQL, runs them read-only against your database, and answers from the real rows. This tour doesn't show pictures — it opens each feature live in front of you. Use the ← → arrow keys to move.",
    spot: null,
    openMenu: null,
  },
  {
    id: "cat",
    title: "Meet DIDA",
    body: "That's her, bottom corner — tail swaying, mood on her face: happy while thinking, sad if something fails. Hover her and she washes her face. Drag her anywhere, or tap her to jump corners. (Her name types itself top-left on every visit.)",
    spot: "cat",
    openMenu: null,
  },
  {
    id: "composer",
    title: "Ask anything",
    body: "This glowing box is where you type — middle of the screen, or docked below once you chat. Press Enter to send, Shift+Enter for a new line, and ↑ recalls previous questions like a terminal. Try a suggestion chip below it right now.",
    spot: "composer",
    openMenu: null,
  },
  {
    id: "ask",
    title: "Question → SQL → answer",
    body: "Go ahead — ask something above for real. The answer lands here with proof attached: expand the SQL inspector to see the exact query, the linked tables, and the raw rows. Never take the words on faith.",
    spot: "messages",
    openMenu: null,
  },
  {
    id: "cancel",
    title: "Changed your mind?",
    body: "While DIDA thinks, a red Cancel pill appears under the dots — press it and the whole operation stops: your wait ends instantly and the server drops the work before its next step, saving nothing to memory.",
    spot: "messages",
    openMenu: null,
  },
  {
    id: "smalltalk",
    title: "She chats too",
    body: "Type hi or ask how she is, right in the same box — small talk is detected up front and answered conversationally with zero database work. Data questions always take the full SQL path instead.",
    spot: "composer",
    openMenu: null,
  },
  {
    id: "memory",
    title: "She remembers",
    body: "Try it: ask “Which singers are from France?” then just “What about from Canada?” — the last 5 turns travel with every question, per chat, even across restarts.",
    spot: "composer",
    openMenu: null,
  },
  {
    id: "dbmenu",
    title: "Pick a database",
    body: "This menu really is open — pick one database to focus it, or leave All databases to search everything at once (each database then answers under its own name).",
    spot: "dock",
    openMenu: "db",
  },
  {
    id: "upload",
    title: "Bring your own data",
    body: "Press “Add your own database” in this open menu and choose a file: SQLite registers directly, CSV and Excel convert automatically (every sheet becomes a table, Arabic included). Invalid files are rejected with a clear reason.",
    spot: "dock",
    openMenu: "db",
  },
  {
    id: "sqleditor",
    title: "Write SQL yourself",
    body: "This editor is live on your selected database, prefilled with SELECT * … LIMIT 5. Press Run (or ⌘/Ctrl+Enter) and watch real rows come back — DROP or DELETE is refused before touching anything.",
    spot: "dock",
    openMenu: "sql",
  },
  {
    id: "schema",
    title: "See the schema",
    body: "Every table with row counts and a filter box, live. Tables DIDA actually used for your last question glow red, so you can see exactly what she looked at.",
    spot: "dock",
    openMenu: "schema",
  },
  {
    id: "table",
    title: "Table deep-dive",
    body: "Click any table in this open list — its full architecture opens: columns with types and keys, relationships, indexes, and real sample rows you can scroll.",
    spot: "dock",
    openMenu: "schema",
  },
  {
    id: "chats",
    title: "Chat history",
    body: "Your real conversations are listed here, each with its own memory and database choice. Switch chats, delete with the trash icon, or start fresh — try switching right now.",
    spot: "dock",
    openMenu: "chats",
  },
  {
    id: "theme",
    title: "Light or dark glass",
    body: "The sun/moon icon flips the whole liquid-glass theme, saved across visits. Go ahead — try it right now, the tour stays open.",
    spot: "navbar",
    openMenu: null,
  },
  {
    id: "done",
    title: "You're ready",
    body: "That's everything, all of it real. Ask a question whenever you're ready — and if you ever get lost, the book icon in the navbar replays this tour.",
    spot: null,
    openMenu: null,
  },
];
