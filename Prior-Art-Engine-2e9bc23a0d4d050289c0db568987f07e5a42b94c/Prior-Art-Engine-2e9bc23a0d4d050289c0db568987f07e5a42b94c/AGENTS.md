# AGENTS.md — prior-art-engine Frontend

Read this file + DESIGN.md fully before writing any code.

## Stack (fixed)

- **React 18** — functional components, hooks
- **Vite** — build tool, dev server with `/api` proxy to backend
- **TypeScript** (`strict: true`)
- **Tailwind CSS v3/v4** — utility-first, CSS-in-JS via className
- **Lucide React** — icons only
- **fetch API** — API client in `src/api/client.js` (sync to backend)
- **CSS Modules or plain CSS** for component styles (no CSS-in-JS libraries)
- **Package manager:** npm only

## Design

All visual decisions are in **DESIGN.md**. Do not invent values — read DESIGN.md first before touching CSS.

## Folder Structure

```
frontend/
├── src/
│   ├── App.jsx                    # Root component
│   ├── main.jsx                   # Entry point
│   ├── styles.css                 # Global styles (oklch tokens, base)
│   ├── api/
│   │   └── client.js              # fetch wrapper for POST /api/search
│   ├── components/
│   │   ├── Stamp.jsx              # Badge (signature element)
│   │   ├── HighlightedAbstract.jsx # Sentence highlighting + best match
│   │   ├── AcademicResultCard.jsx  # Result card for papers
│   │   ├── PatentResultCard.jsx    # Result card for patents
│   │   ├── ArmDCard.jsx            # ARM D extraction display
│   │   ├── GlobalReportSection.jsx # Global report with disclaimer
│   │   ├── PipelineDebugPanel.jsx  # Classifier/keyphrases/concepts
│   │   ├── PatentDiagnosticsPanel.jsx # PatentsView debug table
│   │   ├── ControlsPanel.jsx       # Search settings sidebar
│   │   └── (future: other shared UI)
│   └── vite.config.js             # API proxy config
├── index.html                     # HTML entrypoint
├── public/                        # Static assets
└── package.json
```

## Hard Rules

1. **Never import raw elements inside `src/app/` or `src/`** — all DOM/UI goes in `components/`.
2. **Every component must be functional, typed (no `any`), and pure.** No side effects in render.
3. **No inline styles.** Use className + Tailwind tokens from DESIGN.md only.
4. **No raw hex/hsl colors** — oklch CSS variables only (defined in styles.css).
5. **No `console.log`, `@ts-ignore`, or unused imports.** ESLint must pass.
6. **Named exports everywhere.** Default exports only for route files (`App.jsx`).
7. **No business logic in JSX.** Extract to hooks (`useSearch`, `useSettings`) or separate utils.
8. **No async/await directly in components.** Use a custom hook (`useAsync` pattern) or API client.
9. **API calls only through `src/api/client.js`.** Centralized fetch wrapper + error handling.
10. **Props must be typed** (use JSDoc or TypeScript interfaces if using TS).

## State Rules

**Current approach:** React hooks + props drilling.

- Search state lives in `App.jsx` (form input, settings, loading, results, error).
- Results + debug data pass down as props.
- Settings pass down as props + callback.
- **Future:** if state grows, migrate to Zustand at `src/store/search.js` with selectors.

**Persist to localStorage if needed:**
```jsx
// In App.jsx, after settings change
useEffect(() => {
  localStorage.setItem('searchSettings', JSON.stringify(settings));
}, [settings]);

// On mount
const [settings, setSettings] = useState(() => {
  const saved = localStorage.getItem('searchSettings');
  return saved ? JSON.parse(saved) : DEFAULT_SETTINGS;
});
```

## Component Patterns

### API Client (`src/api/client.js`)

```jsx
const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export async function runSearch(payload) {
  const res = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}
```

**Rule:** All HTTP calls route through this file. Do not `fetch()` directly from components.

### Form Component Pattern

```jsx
export default function SearchForm({ loading, onSubmit }) {
  const [idea, setIdea] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!idea.trim() || loading) return;
    onSubmit(idea);
  }

  return (
    <form onSubmit={handleSubmit}>
      <textarea
        value={idea}
        onChange={(e) => setIdea(e.target.value)}
        placeholder="..."
        className="h-32 w-full rounded-lg border border-line bg-paper-raised px-3 text-sm text-ink placeholder:text-faint focus:outline-none focus:ring-1 focus:ring-signal"
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !idea.trim()}
        className="h-9 rounded-md bg-ledger px-4 text-sm font-600 text-white hover:bg-ledger-soft transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "Searching…" : "Search prior art"}
      </button>
    </form>
  );
}
```

### Result Card Pattern

```jsx
export default function ResultCard({ result, highlight }) {
  return (
    <div className="rounded-lg border border-line bg-paper-raised overflow-hidden">
      <div className="border-l-4 border-l-ledger px-5 py-4">
        <h3 className="font-serif text-lg font-600 text-ink">{result.title}</h3>
        <div className="mt-2 flex items-center justify-between gap-4">
          <div className="text-xs text-muted">📅 {result.date}</div>
          <Stamp pct={result.fused_pct} />
        </div>
      </div>
      <div className="border-t border-line bg-paper px-5 py-4">
        {/* Highlight body */}
      </div>
    </div>
  );
}
```

### Conditional Rendering

```jsx
// Use ternary for simple cases
{data ? <Results data={data} /> : <EmptyState />}

// Use early return for complex guards
if (loading) return <LoadingIndicator />;
if (error) return <ErrorBanner error={error} />;
if (!data) return <EmptyState />;
return <Results data={data} />;
```

## API Integration

**Search request schema:**
```json
{
  "idea": "string",
  "max_display": 3–10,
  "effective_threshold": 10–50,
  "highlight_threshold_pct": 60–95,
  "retrieval_mode": "Concept + Full-Text (Recommended)|Full-Text Only|Concept-Based Only",
  "enable_patent_search": boolean,
  "enable_arm_d": boolean,
  "enable_global_report": boolean
}
```

**Response:** One flat JSON with academic results, patent results, debug info, and global report. See `app/pipeline/search_service.py` for the exact shape.

**Error handling:**
```jsx
try {
  const data = await runSearch({ idea, ...settings });
  setData(data);
} catch (err) {
  setError(err.message);
  setData(null);
}
```

## Workflow

1. **Read DESIGN.md fully** — don't skip.
2. **Identify the component** to build (e.g., "HighlightedAbstract").
3. **Write the component** in isolation at `src/components/`.
   - Props fully typed (JSDoc or TS).
   - No API calls.
   - Render logic only.
4. **Test in App.jsx** — pass mock data, verify styling.
5. **Run `npm run build`** — must pass.
6. **Run `npm run lint`** (if configured) — zero errors.
7. **Test in browser** — dark mode, responsive, focus states.

## Definition of Done

### Per Component
- [ ] Component renders without error
- [ ] Props are typed (JSDoc or TypeScript)
- [ ] Tailwind classes match DESIGN.md spec
- [ ] Dark mode is verified (it's the default)
- [ ] Focus-visible states work (Tab key)
- [ ] Icon-only buttons have `aria-label`
- [ ] No console.log or `@ts-ignore`
- [ ] No unused imports

### Per Feature (Search)
- [ ] `npm run dev` starts clean, no errors
- [ ] `npm run build` passes
- [ ] Form input works, loads state on mount if persisted
- [ ] Search button fires `runSearch()` to backend
- [ ] Results render with correct styling
- [ ] Tabs switch between Academic/Patent
- [ ] Dark mode is the default
- [ ] All interactive elements (buttons, inputs, tabs) are keyboard-accessible (Tab, Enter)
- [ ] Error states display correctly (500 errors, network failures, timeouts)
- [ ] Empty state displays when no results
- [ ] Highlights render correctly (yellow background on sentences)
- [ ] "Best sentence" callout displays
- [ ] Stamps show correct match percentages
- [ ] Global report section shows with disclaimer

## Naming Conventions

- **Components:** PascalCase, e.g., `SearchForm.jsx`, `ResultCard.jsx`
- **Hooks:** camelCase, prefix `use`, e.g., `useSearch.js`, `useAsync.js`
- **Utils:** camelCase, e.g., `api/client.js`, `lib/utils.js`
- **CSS classes:** kebab-case (Tailwind), scoped in component
- **Props:** camelCase, e.g., `onSubmit`, `isLoading`

## Performance Notes

- **Debounce slider inputs** if they trigger re-renders (not critical for v1)
- **Memoize result lists** if > 100 items (use `React.memo`)
- **Lazy load images** if used (not applicable now)
- **Code split** if the app grows (Vite does this automatically)

## Testing (optional for v1)

If tests are added:
- Unit tests for API client (`api/client.test.js`)
- Snapshot tests for components (optional)
- Run `npm test` as part of CI/CD

## What NOT to do

- ❌ `const App = () => <div>...</div>` — use `function App()`
- ❌ Prop drilling > 2 levels — refactor to custom hook or context
- ❌ Async/await directly in JSX — extract to a hook
- ❌ `useState` for form-heavy apps without a proper state library (use Zustand if it grows)
- ❌ Inline event handlers — extract to named functions for debuggability
- ❌ `tabIndex="-1"` unless you have a very good reason
- ❌ Color values as strings — always use CSS variables
- ❌ Multiple className strings — use template literals or cn() if you add it
- ❌ Comments explaining obvious code — let the code speak for itself
