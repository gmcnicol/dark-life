# Web

This Next.js 15 app uses React 19, Tailwind CSS 4 and shadcn/ui.

## Scripts

- `pnpm dev` – start the development server.
- `pnpm build` – build the production bundle.
- `pnpm start` – run the production server.
- `pnpm lint` – run ESLint with Prettier.
- `pnpm test` – run unit tests with Vitest.
- `pnpm e2e` – run Playwright end-to-end tests.
- `pnpm typecheck` – run TypeScript without emitting output.

## Features

- `/board` Kanban board with drag-and-drop status updates.
- Global shortcuts: `g i` (inbox), `g b` (board), `/` focuses the header search box.
- Structured logs when `NEXT_PUBLIC_DEV_LOGGING=true`.

Run Lighthouse against the board after building:

```bash
pnpm build && pnpm start &
npx lighthouse http://localhost:3000/board --quiet --chrome-flags="--headless"
```
