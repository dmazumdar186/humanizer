# Humanizer — Strip AI-Tells, Rewrite in Your Voice

Takes AI-generated text and rewrites it in a personal voice profile, stripping AI-tells like em-dashes, "Certainly!", "delve", and "leverage" before you send it as a message. Goes beyond simple find-and-replace: a deterministic pre-pass + LLM rewrite with tool-use structured output, guided by real writing samples from your own past messages.

One key. Three providers. The Gemini free path costs $0.00 per run.

---

## Demo

**INPUT:**
```
Certainly! I'd be happy to delve into this comprehensive analysis of distributed databases.
```

**OUTPUT:**
```
let's look at this analysis of distributed databases.
```

Generated for $0.00 via Gemini free tier (`--tier gemini`). The deterministic pre-pass stripped "Certainly! I'd be happy to" before the LLM even saw the text — the LLM only had to rewrite the substantive sentence in the target voice.

---

## Quick Start

```bash
git clone https://github.com/dmazumdar186/humanizer.git
cd humanizer
pip install -r requirements.txt
cp .env.example .env  # add OPENROUTER_API_KEY or GEMINI_API_KEY
```

**Free path (Gemini direct, $0.00):**
```bash
py humanizer.py --text "Certainly! I'd be happy to help." --tier gemini
```

**Default path (Claude Sonnet via OpenRouter, ~$0.0015):**
```bash
py humanizer.py --text "Certainly! I'd be happy to help."
```

**Dry-run (no API call, see pre-pass + cost estimate):**
```bash
py humanizer.py --text "Certainly! I'd be happy to help." --dry-run
```

---

## The Three Tiers

| Tier | Key Required | Cost | Model |
|------|-------------|------|-------|
| `default` | `OPENROUTER_API_KEY` | ~$0.0015/run | Claude Sonnet (latest) |
| `premium` | `OPENROUTER_API_KEY` | ~$0.004/run | Claude Opus (latest) |
| `gemini` | `GEMINI_API_KEY` | **$0.00** | Gemini Flash (latest) |

If you set both `GEMINI_API_KEY` and `OPENROUTER_API_KEY`, `--tier gemini` always routes to the free Gemini direct path.

---

## Key Technical Features

- **4-stage pipeline:** deterministic pre-pass (free) → voice profile lookup (free) → LLM rewrite via tool-use (cheap or free) → platform post-processing. The pre-pass strips obvious AI-tells before any token is spent.

- **Voice profiles:** JSON files in `voices/` with real writing samples that teach the LLM your actual cadence. Not generic "be more casual" prompts — verbatim sentences from your own messages. The more examples, the better the style match.

- **Multi-provider routing:** one `OPENROUTER_API_KEY` reaches Claude, GPT, and Gemini via OpenRouter's unified API. Add `GEMINI_API_KEY` for the $0.00 direct path. Add `ANTHROPIC_API_KEY` for the legacy direct Anthropic path. Provider is auto-detected from whichever keys are present.

- **Dynamic model registry:** tier→model-ID resolved at runtime via each provider's models API, 7-day local cache, ALLOWED_FAMILIES allowlist. Picks up new models (e.g. `gemini-2.5-flash`, `claude-sonnet-4-6`) without code changes. Falls back through cache → LAST_KNOWN_GOOD; never crashes on a missing key.

- **Tool-use structured output:** forces a reliable JSON schema via `submit_humanized` function-calling (OpenAI/OpenRouter format, Anthropic format, Gemini function-calling). No regex parsing of free-text responses — the LLM must return structured output or the call fails cleanly.

- **Platform-aware post-process:** LinkedIn strips markdown (`**bold**`, `# headings`, backtick code, `[link](url)`). Slack converts bold to italic and keeps code spans. Tweet hard-caps at 280 characters. Email preserves paragraph structure. Generic passes through with only max-length enforcement.

---

## CLI Reference

```
usage: humanizer [-h] [--text TEXT | --file PATH]
                 [--voice VOICE] [--platform {linkedin,email,slack,tweet,generic}]
                 [--max-length N] [--show-diff] [--keep-em-dashes]
                 [--tier {default,premium,gemini}] [--dry-run]

options:
  --text TEXT           Direct text input
  --file PATH           Path to a file to humanize
  --voice VOICE         Voice profile name (default: debanjan)
  --platform            Target platform: linkedin | email | slack | tweet | generic
  --max-length N        Character cap on output (tweet defaults to 280)
  --show-diff           Print before/after to stderr
  --keep-em-dashes      Skip em-dash replacement
  --tier                Model tier: default (Sonnet) | premium (Opus) | gemini (free)
  --dry-run             Skip LLM call; show pre-pass output and cost estimate
```

Stdin is also supported when `--text` and `--file` are both omitted:
```bash
echo "Certainly! Let me delve into this." | py humanizer.py --tier gemini
```

---

## Adding a Voice

Copy the template and fill in the fields:

```bash
cp voices/_template.json voices/yourname.json
```

The `examples` field is the most important. Add 5–10 real sentences you have written, verbatim — opinions, observations, statements. Not imperative commands. The more natural and varied the examples, the better the LLM can match your cadence.

```json
{
  "name": "yourname",
  "display_name": "Your Name",
  "description": "One-line description of your writing style",
  "traits": {
    "sentence_length": "short punchy sentences, rarely > 20 words",
    "register": "direct, no marketing-speak",
    "punctuation": "minimal exclamation marks",
    "formatting": "prose over bullets unless there is a real list"
  },
  "lexicon": {
    "uses": ["yeah", "actually", "right"],
    "avoids": ["Certainly", "delve", "leverage", "robust", "I'd be happy to"]
  },
  "examples": [
    "yeah do it",
    "added both, check now",
    "why just for Anthropic? same goes for Gemini too."
  ]
}
```

Then use it:
```bash
py humanizer.py --text "Certainly! I'd be happy to help." --voice yourname
```

---

## Testing

107 tests across 8 files. 11-round adversarial audit loop caught 30+ bugs before shipping.

| File | Tier | Description |
|------|------|-------------|
| `tests/test_unit.py` | Unit | Pre-pass regex, voice loader, platform post-process, CLI contract |
| `tests/test_integration.py` | Integration | Pre-pass → prompt round-trip, provider detection, model registry, real Gemini probe |
| `tests/test_e2e.py` | E2E | Full subprocess invocations, regression guards for R6/R8/R10 bugs |
| `tests/test_sanity.py` | Sanity | Import check, --help flags, dep importability, JSON validity, secret leakage |
| `tests/test_performance.py` | Performance | Wall-clock thresholds, adversarial regex, cost estimate bounds, concurrent dry-runs |
| `tests/test_monkey.py` | Monkey/Chaos | Empty input, 50KB input, path traversal, binary stdin, tampered cache, invalid flags |
| `tests/test_resilience.py` | Resilience | Missing voice file, corrupt cache, invalid API key, offline dry-run |
| `tests/canary_check.py` | Canary | Structured JSON health report: secrets, deps, voices, pre-pass, model registry, LLM smoke |

Run fast tests (no LLM calls):
```bash
py tests/test_unit.py
py tests/canary_check.py
py -m pytest tests/test_sanity.py tests/test_monkey.py -v
```

Run all (some require API keys):
```bash
py -m pytest tests/ -v -s
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in at least one key:

```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...   # https://openrouter.ai/keys
GEMINI_API_KEY=AIza...             # https://aistudio.google.com/apikey
```

Model registry cache is written to `.tmp/model_registry.json` (gitignored, 7-day TTL). Delete it to force a re-fetch.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built with [Claude Code](https://claude.ai/claude-code)*
