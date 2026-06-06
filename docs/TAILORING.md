# Resume Tailoring

How Carrera turns your base CV + a job posting into a tailored application — and how to choose the right provider.

## What happens when you click "Tailor Resume"

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Base CV     │     │  Job posting    │     │  Your emphasis   │
│  (CVData)    │     │  (description)  │     │  + instructions  │
└──────┬───────┘     └────────┬────────┘     └────────┬─────────┘
       │                      │                       │
       └──────────┬───────────┴───────────────────────┘
                  ▼
      ┌────────────────────────┐
      │  Analyzer              │  → required_skills, preferred_skills,
      │  (regex + heuristics)  │    responsibilities, language,
      │                        │    match_score
      └─────────┬──────────────┘
                │
                ▼
      ┌────────────────────────┐       ┌──────────────────┐
      │  Provider dispatch     │◀──────│  User picks:     │
      │                        │       │  template /      │
      │  template              │       │  ollama /        │
      │  ollama                │       │  openai /        │
      │  openai                │       │  anthropic       │
      │  anthropic             │       └──────────────────┘
      └─────────┬──────────────┘
                │
                ▼
      ┌────────────────────────┐
      │  TailoredOutput        │  → resume_data (CVData)
      │                        │    cover_letter (str)
      └─────────┬──────────────┘
                │
                ▼
      ┌────────────────────────┐
      │  PDF generator         │  → resume.pdf + cover_letter.pdf
      │  (ReportLab)           │
      └────────────────────────┘
```

The analyzer runs every time (it's free and fast). The provider is what you pick. The PDF step is always last.

## Choosing a provider

| Provider | Cost | Speed | Quality | When to use |
|---|---|---|---|---|
| **Template** | $0 | instant | Good for well-structured CVs, predictable | Default for junior/mid roles; when you want determinism |
| **Ollama** | $0 (local) | 10–60s | Matches model quality (llama3 ≈ GPT-3.5-ish) | Daily driver if you have a decent GPU / Mac |
| **OpenAI** | ~$0.01–0.05 | 5–15s | Very good (gpt-4o-mini) | High-stakes applications |
| **Anthropic** | ~$0.01–0.05 | 5–15s | Very good (claude-haiku-4-5) | Prefer Claude's tone / you already have a key |

The UI shows an **estimated cost** before any paid call. Nothing runs until you click confirm.

## What the providers actually do

### Template

Pure Python, zero dependencies on any model.

- **Bullet ranking**: each experience bullet gets scored by keyword overlap with the job's required_skills + preferred_skills (fuzzy match via `fuzzywuzzy`). Top 4 per role are kept.
- **Summary rewrite**: takes your base summary, injects the top 2 JD-relevant skills if they're in your skills list, appends a target-role phrase.
- **Cover letter**: fills an `ApplicationTemplate` — variables are `{company}`, `{role}`, `{top_skills}`, `{relevant_experience}`. Templates are seeded in PT and EN; edit them in the UI.

Deterministic and fast. Doesn't hallucinate. Won't invent bullets you didn't write.

### Ollama (local LLM)

POSTs to `http://localhost:11434/api/generate` (configurable via `OLLAMA_BASE_URL`).

Default model is `llama3`. Set `OLLAMA_MODEL` in `.env` to pick another — `mistral`, `gemma`, `qwen2.5`, whatever you've pulled. Carrera doesn't ship with models; run `ollama pull <name>` once.

The prompt includes: your base CV (as JSON), the job description, your emphasis list, and explicit constraints ("use only facts present in the base CV"). The provider then JSON-parses the response and merges it back into `CVData`.

If Ollama isn't running, the call fails cleanly and the UI suggests switching to template.

### OpenAI / Anthropic

Direct HTTPX calls — no SDK. Authentication is just the Bearer / `x-api-key` header.

The prompt is structurally the same as Ollama's but tuned for the model's system-prompt format. Token estimates come from a conservative char-count heuristic (input: `len(prompt) / 3.5`, output: `800` tokens). Real cost is pulled from the API response after the fact.

**Supported models** (edit `_COST_PER_1K_TOKENS` in `tailoring_engine.py` to add more):

| Provider | Model | Input $/1K | Output $/1K |
|---|---|---|---|
| OpenAI | gpt-4o-mini (default) | $0.00015 | $0.0006 |
| OpenAI | gpt-4o | $0.0025 | $0.010 |
| Anthropic | claude-haiku-4-5-20251001 (default) | $0.001 | $0.005 |
| Anthropic | claude-sonnet-4-5 | $0.003 | $0.015 |

A normal tailoring run (a ~2000-token JD + your ~1500-token CV) costs about:
- gpt-4o-mini: ~$0.001
- claude-haiku-4-5: ~$0.005
- gpt-4o: ~$0.02
- claude-sonnet-4-5: ~$0.015

## Keeping tailoring honest

**Rule: every bullet in the output must trace back to the base CV.** If a model invents experience, it's worse than useless — it'll get you caught in an interview.

How we enforce this:

- The prompt explicitly says "Use ONLY facts and experience present in the provided base CV. Do not invent numbers, companies, or dates."
- The response is JSON-parsed and the experience array is reconciled against the base CV by `(company, title, start_date)` tuple — unknown tuples are dropped.
- Skills not in your base skills list are filtered out before saving.

## Output location

PDFs go to `PDF_OUTPUT_DIR` (default `./data/pdfs/` in dev, `~/.carrera/pdfs/` in the frozen exe). Filenames are `tailored_<application_id>_resume.pdf` and `..._cover_letter.pdf`.

Files are never overwritten — if you re-tailor the same job you get a new `TailoredApplication` row and a new PDF pair. Old versions stay on disk until you clean up manually.

## Extending

Want to add a new provider (Gemini, Mistral AI, a local vLLM server)?

1. Add a branch in `tailor_resume()` dispatcher.
2. Implement `_tailor_with_<provider>()` — returns a `TailoredOutput`.
3. Add your model's per-token price to `_COST_PER_1K_TOKENS`.
4. Add the provider to `TailoringRequest.ai_provider` literal in `frontend/src/types/index.ts`.
5. Add it to the `AI_PROVIDERS` list in `TailoringWorkflow.tsx`.
