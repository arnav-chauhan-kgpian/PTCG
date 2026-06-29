# Pokémon AI — Frontend

Premium Next.js 15 + React 19 + TypeScript + Tailwind frontend for the
**Pokémon AI** platform. Dark-mode-first, glassmorphic, fully responsive.

## What's inside

- **Landing page** — animated hero, feature grid, architecture diagram, performance numbers, live demo, testimonials, CTA, footer.
- **Dashboard** — live metrics, training loss + Elo charts, recent activity, system health.
- **Battle Arena** — Pokémon TCG Live-inspired board with prize cards, bench, hand,
  log, and an MCTS decision panel showing top moves, visit counts, win probability, and PV.
- **Deck Builder** — instant search over 1,267 cards, click-to-add, energy curve, AI generation.
- **Deck Analyzer** — paste a deck list, get archetype + consistency + synergy + recommendations.
- **Card Database** — premium filterable explorer with detail modal.
- **Game Analysis** — explainable MCTS decisions, principal variation, expected prize swing.
- **Training** — live loss curves, arena Elo, promotion history.
- **Benchmarks** — performance breakdown across the stack, historical trend, reproduce hint.
- **Settings**, **About**, **404**, **500**, **command palette (⌘K)**.

## Stack

| Concern | Tooling |
|---|---|
| Framework | Next.js 15 (App Router) |
| UI | React 19 · TypeScript · Tailwind CSS · shadcn-style primitives · Radix UI |
| Motion | Framer Motion |
| Data | TanStack Query · Zustand |
| Charts | Recharts |
| Forms | React Hook Form · Zod |
| Icons | Lucide |
| Theming | next-themes (dark default) |
| Notifications | Sonner |

## Quick start

```bash
cd frontend
cp .env.example .env.local

npm install
npm run dev                # → http://localhost:3000
```

Start the Python backend separately (`pokemon-ai serve` or `python -m src.cli serve`) on port 8000.
Requests prefixed with `/api/backend/*` are proxied through Next's rewrite to that server.

## Scripts

```bash
npm run dev         # dev server with Turbopack
npm run build       # production build
npm run start       # serve production build
npm run lint        # ESLint
npm run typecheck   # tsc --noEmit
npm run format      # Prettier
```

## Environment variables

| Name | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI backend root |
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` | Frontend canonical URL (SEO) |

## Architecture

```
src/
  app/                    Next.js App Router
    page.tsx              Landing page
    (app)/                Authenticated app shell
      dashboard, battle, deck-builder, deck-analyzer, cards,
      analysis, training, benchmarks, settings, about
    not-found.tsx, error.tsx, globals.css

  components/
    ui/                   Primitives (button, card, dialog, …)
    shared/               Brand library (MetricCard, GlassPanel, EnergyIcon, Sidebar, Topbar, …)
    landing/              Landing page sections
    battle/               Battle UI components
    charts/               Recharts wrappers
    command/              ⌘K palette

  features/               (reserved for cross-cutting features)
  hooks/                  Custom hooks (useKeyboardShortcut, …)
  lib/api/                Typed API client + endpoints
  services/               Backend services (mockable, swap to real endpoints)
  providers/              Theme, query, command-palette
  store/                  Zustand stores
  types/                  Shared TypeScript types
  config/                 Site, navigation
  styles/                 (reserved for global styles)
```

## Deployment

The project is ready for any of:

- **Vercel** — `vercel deploy`. Set `NEXT_PUBLIC_API_URL` to the backend's public origin.
- **Cloudflare Pages** — `npm run build`, deploy the `.next` output.
- **Netlify** — same.
- **Docker** — works alongside the backend image; expose port 3000 and proxy backend at `/api/backend/*`.

## Design language

- Glassmorphism (`backdrop-blur-xl` + soft borders + ambient gradients)
- Spring-animated transitions (Framer Motion)
- Brand gradient: electric blue → indigo → purple → gold
- Pokémon energy-type colors mapped to Tailwind utilities
- Tasteful particle backgrounds in hero and CTAs
- Custom skeleton loading via shimmer animation
- Smooth focus rings, accessible by default
- Mobile-first responsive layout

## API integration

All backend calls go through `src/lib/api/client.ts` → `src/lib/api/endpoints.ts`.
Endpoints already wired up:

- `POST /move` · `POST /evaluate` · `POST /deck/analyze` · `POST /deck/build`
- `GET /health` · `GET /metrics`

UI surfaces that need data not yet exposed by the backend (dashboard summary,
training telemetry, benchmark history, card database) consume `src/services/*.ts`
which expose typed interfaces. Swap the mock implementations to real endpoints
without touching the components.
