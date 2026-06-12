# CLAUDE.md — humanizer repo

Agent instructions for Claude Code when working in this repo.

---

## Architecture

4-stage pipeline (all in `humanizer.py`, flat layout — no src/ directory):

1. **Deterministic pre-pass** — regex strips opening/closing fluff, em-dashes, triple-parallel
   constructs, hedge phrases, and banned vocab. Source of truth: `DEFAULT_BANNED_VOCAB` + regex
   constants at top of `humanizer.py`. AI-tell patterns live in code, not a data file.
2. **Voice profile lookup** — loads `voices/<name>.json`. Guards: `.resolve()` +
   `is_relative_to(VOICES_DIR)` path traversal check. Fails fast on missing/corrupt JSON.
3. **LLM rewrite via tool-use** — forces `submit_humanized` function-call schema (structured
   output). Three provider paths: OpenRouter (OR key) → Anthropic direct (ANTHROPIC key) →
   Gemini direct (GEMINI key, free). Model IDs resolved at runtime via `model_registry.py`.
4. **Platform post-processing** — strips/converts markdown per target platform
   (linkedin/email/slack/tweet/generic), enforces `--max-length`.

Sibling module: `model_registry.py` — resolves tier→model-ID at runtime, 7-day cache in
`.tmp/model_registry.json`. Delete cache to force re-fetch.

---

## Entry points

```bash
# Direct invocation (flat repo — no package install needed)
py humanizer.py --text "Certainly! Let me delve into this." --tier gemini
py humanizer.py --file input.txt --voice debanjan --platform linkedin
echo "AI text" | py humanizer.py --dry-run

# Key flags
--tier {default,premium,gemini}    # Sonnet / Opus / Gemini free
--voice <name>                     # voices/<name>.json (default: debanjan)
--platform {linkedin,email,slack,tweet,generic}
--dry-run                          # skip LLM; show pre-pass + cost estimate
--show-diff                        # print before/after to stderr
--max-length N                     # char cap (tweet defaults to 280)
--keep-em-dashes                   # skip em-dash replacement
```

---

## Tests

No `pyproject.toml`. Run with:

```bash
py -m pytest tests/ -v              # all tests (some require API keys)
py -m pytest tests/test_sanity.py tests/test_monkey.py -v   # fast, no LLM
py tests/test_unit.py               # unit tests (direct run, no pytest)
py tests/canary_check.py            # structured JSON health report to stdout
```

Test tiers:

| File | Type | LLM needed |
|------|------|-----------|
| `tests/test_unit.py` | Unit | No |
| `tests/test_sanity.py` | Sanity | No |
| `tests/test_monkey.py` | Monkey/Chaos | No (dry-run only) |
| `tests/test_performance.py` | Performance | Gemini (one test) |
| `tests/test_integration.py` | Integration | Gemini (one probe) |
| `tests/test_e2e.py` | E2E | Yes |
| `tests/test_resilience.py` | Resilience | No (error paths) |
| `tests/canary_check.py` | Canary | Optional (Gemini smoke) |

---

## Tier routing

- `default` → Claude Sonnet (latest) via OpenRouter (`OPENROUTER_API_KEY`)
- `premium` → Claude Opus (latest) via OpenRouter (`OPENROUTER_API_KEY`)
- `gemini` → Gemini Flash (latest) direct (`GEMINI_API_KEY`, **$0.00**)
- Fallback chain: OR key missing → Anthropic direct (`ANTHROPIC_API_KEY`) → fail.

---

## Voice profiles

Location: `voices/` directory. Template: `voices/_template.json`.

Key fields: `name`, `display_name`, `description`, `traits`, `lexicon` (`uses`/`avoids`),
`examples` (5–10 real verbatim sentences — most important field).

To add a voice:
```bash
cp voices/_template.json voices/yourname.json
# fill in examples with real sentences you've written
py humanizer.py --text "test" --voice yourname --dry-run
```

---

## Cost tracking

`_TIER_COST_PER_M` (in `humanizer.py`) holds 4 entries per tier:
`input`, `cache_read` (0.1× input), `cache_write` (1.25× input), `output`.

Cost-calc accepts all 4 token fields from `response.usage`:
- OpenRouter: `prompt_tokens`, `completion_tokens` (cache fields default 0 if absent)
- Anthropic: `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens`

Flat input+output only would over-estimate 5–10× under prompt caching.

---

## Windows quirks

- `humanizer.py` reconfigures `sys.stdout` and `sys.stderr` to UTF-8 at import time (lines
  33–37). If you fork the file, preserve this block — Windows cp1252 crashes on bytes >= 0x80.
- Every `subprocess.run(..., text=True)` call must include `encoding="utf-8", errors="replace"`.
  This is enforced in all test files and `canary_check.py`.
- Use `py` not `python3` on this machine.

---

## Workspace skill coordination

The workspace skill at
`AntiGravity Project Space/directives/content/humanizer.md`
calls into this repo. Any CLI flag rename or removal must be mirrored there.

Changes that require SKILL.md update: any new flag, any renamed flag, new `--batch` or
`--council` mode. Changes that do NOT require SKILL.md update: internal cost-calc, pricing
tables, test changes, documentation.

---

## AI-tell patterns

Source of truth: `DEFAULT_BANNED_VOCAB` list + regex constants (`RE_OPENING_FLUFF`,
`RE_CLOSING_FLUFF`, `RE_EM_DASH`, `RE_TRIPLE_PARALLEL`, `RE_TWO_PART_BUT_ALSO`, `RE_HEDGES`)
at the top of `humanizer.py`. Add new patterns there, not in a separate data file (no
`data/ai_tells.json` exists — all patterns are inline).
