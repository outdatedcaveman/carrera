"""Tailoring engine — analyze job requirements and generate tailored resume + cover letter."""
import json
import logging
import re
from typing import Any
import httpx
from ..config import get_settings
from . import settings_store
from ..schemas import JobRequirementsAnalysis, CostEstimate
from ..models import Job

logger = logging.getLogger(__name__)
settings = get_settings()


class TailoringError(Exception):
    pass


# ── Job Analysis ───────────────────────────────────────────────────────────────

def analyze_job_requirements(description: str, cv_data: dict) -> JobRequirementsAnalysis:
    """Parse job description and compare against CV. Returns structured analysis."""
    desc_lower = description.lower()

    required_skills = _extract_skills(description, required=True)
    preferred_skills = _extract_skills(description, required=False)
    responsibilities = _extract_responsibilities(description)
    culture_keywords = _extract_culture_keywords(description)
    seniority = _detect_seniority(description)
    language = _detect_language(description)

    cv_skills = [s.lower() for s in cv_data.get("skills", [])]
    cv_text = " ".join([
        " ".join(exp.get("bullets", [])) + " " + " ".join(exp.get("keywords", []))
        for exp in cv_data.get("experience", [])
    ]).lower()

    matching_experience = []
    for i, exp in enumerate(cv_data.get("experience", [])):
        exp_text = " ".join(exp.get("bullets", []) + exp.get("keywords", [])).lower()
        matched_skills = [s for s in required_skills + preferred_skills if s.lower() in exp_text]
        if matched_skills:
            matching_experience.append({
                "index": i,
                "company": exp.get("company"),
                "title": exp.get("title"),
                "matched_skills": matched_skills,
                "relevance_score": len(matched_skills),
            })

    matching_experience.sort(key=lambda x: x["relevance_score"], reverse=True)

    all_required_lower = [s.lower() for s in required_skills]
    skill_gaps = [s for s in all_required_lower if s not in cv_text and s not in cv_skills]

    all_matched = set(s.lower() for m in matching_experience for s in m["matched_skills"])
    match_score = len(all_matched) / max(len(required_skills + preferred_skills), 1)
    match_score = min(1.0, match_score)

    return JobRequirementsAnalysis(
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        responsibilities=responsibilities[:8],
        culture_keywords=culture_keywords,
        seniority_level=seniority,
        language_detected=language,
        matching_experience=matching_experience,
        skill_gaps=skill_gaps[:6],
        match_score=round(match_score, 2),
    )


def _extract_skills(text: str, required: bool) -> list[str]:
    skills_pool = [
        "Excel", "PowerPoint", "Word", "Google Workspace", "Jira", "Miro", "Trello",
        "SQL", "Python", "Power BI", "Tableau", "Salesforce", "SAP", "ERP",
        "project management", "gestão de projetos", "product management",
        "business analysis", "análise de negócios", "financial modeling",
        "modelagem financeira", "data analysis", "análise de dados",
        "stakeholder management", "gestão de stakeholders",
        "strategic planning", "planejamento estratégico",
        "business development", "desenvolvimento de negócios",
        "budget management", "controle orçamentário",
        "KPI", "OKR", "agile", "scrum", "kanban",
        "marketing", "branding", "CRM", "B2B", "B2C",
        "innovation", "inovação", "entrepreneurship", "empreendedorismo",
        "program management", "gestão de programas",
        "financial closing", "fechamento financeiro",
        "real estate", "portfólio", "portfolio",
    ]

    text_lower = text.lower()
    found = []
    for skill in skills_pool:
        if skill.lower() in text_lower:
            if required:
                ctx = text_lower[max(0, text_lower.find(skill.lower()) - 100):text_lower.find(skill.lower()) + 50]
                req_indicators = ["required", "must", "obrigatório", "necessário", "requisito", "exigido"]
                if any(ind in ctx for ind in req_indicators):
                    found.append(skill)
            else:
                found.append(skill)

    if not required and not found:
        for skill in skills_pool:
            if skill.lower() in text_lower:
                found.append(skill)

    return list(dict.fromkeys(found))[:12]


def _extract_responsibilities(text: str) -> list[str]:
    lines = text.split("\n")
    responsibilities = []
    in_section = False

    resp_headers = ["responsabilidades", "responsibilities", "atividades", "activities", "o que você vai fazer", "what you'll do"]

    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        if any(h in line_lower for h in resp_headers):
            in_section = True
            continue

        if in_section and line_stripped.startswith(("-", "•", "*", "·")):
            resp = line_stripped.lstrip("-•*· ").strip()
            if 15 < len(resp) < 200:
                responsibilities.append(resp)

        if in_section and len(responsibilities) >= 10:
            break

    return responsibilities


def _extract_culture_keywords(text: str) -> list[str]:
    culture_terms = [
        "colaborativo", "collaborative", "dinâmico", "dynamic", "inovador", "innovative",
        "ágil", "agile", "startup", "scale-up", "impacto", "impact",
        "diversidade", "diversity", "inclusão", "inclusion",
        "crescimento", "growth", "aprendizado", "learning",
        "autonomia", "autonomy", "resultado", "result-oriented",
    ]
    text_lower = text.lower()
    return [t for t in culture_terms if t.lower() in text_lower][:6]


def _detect_seniority(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["director", "diretor", "vp ", "vice president"]):
        return "Director/VP"
    if any(w in text_lower for w in ["senior", "sênior", "sr.", "lead", "líder"]):
        return "Senior"
    if any(w in text_lower for w in ["pleno", "mid-level", "mid level", "analista pleno"]):
        return "Mid-level"
    if any(w in text_lower for w in ["junior", "júnior", "jr.", "entry"]):
        return "Junior"
    if any(w in text_lower for w in ["manager", "gerente", "head"]):
        return "Manager"
    return "Mid-level"


def _detect_language(text: str) -> str:
    pt_words = ["você", "empresa", "vaga", "candidato", "requisitos", "benefícios", "experiência"]
    pt_count = sum(1 for w in pt_words if w in text.lower())
    return "pt" if pt_count >= 2 else "en"


# ── Cost Estimation ────────────────────────────────────────────────────────────

def estimate_cost(provider: str, model: str | None, job_description: str, cv_data: dict) -> CostEstimate:
    input_tokens = (len(job_description) + len(json.dumps(cv_data))) // 4
    output_tokens = 2000

    model = model or _default_model(provider)

    COST_PER_1K = {
        "openai:gpt-4o-mini": (0.00015, 0.0006),
        "openai:gpt-4o": (0.005, 0.015),
        "anthropic:claude-haiku-4-5-20251001": (0.00025, 0.00125),
        "anthropic:claude-sonnet-4-6": (0.003, 0.015),
    }

    key = f"{provider}:{model}"
    if key in COST_PER_1K:
        in_price, out_price = COST_PER_1K[key]
        cost = (input_tokens / 1000) * in_price + (output_tokens / 1000) * out_price
    else:
        cost = 0.0

    return CostEstimate(
        provider=provider,
        model=model,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        estimated_cost_usd=round(cost, 4),
        free=provider in ("template", "ollama"),
    )


def _default_model(provider: str) -> str:
    defaults = {
        "ollama": settings.ollama_model,
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
    }
    return defaults.get(provider, "unknown")


# ── Generation ─────────────────────────────────────────────────────────────────

async def generate_tailored_application(
    job: Job,
    base_resume_data: dict,
    ai_provider: str,
    ai_model: str | None,
    language: str,
    emphasis: list[str],
    custom_instructions: str,
) -> dict:
    """Entry point for tailoring. Returns dict with resume_data, cover_letter, model_used, cost_usd, notes."""
    analysis = analyze_job_requirements(job.description, base_resume_data)

    if ai_provider == "template":
        return _template_tailor(job, base_resume_data, analysis, language, emphasis)

    model = ai_model or _default_model(ai_provider)

    if ai_provider == "ollama":
        return await _ollama_tailor(job, base_resume_data, analysis, language, emphasis, model, custom_instructions)
    elif ai_provider == "openai":
        return await _openai_tailor(job, base_resume_data, analysis, language, emphasis, model, custom_instructions)
    elif ai_provider == "anthropic":
        return await _anthropic_tailor(job, base_resume_data, analysis, language, emphasis, model, custom_instructions)

    raise TailoringError(f"Unknown AI provider: {ai_provider}")


def _template_tailor(job: Job, cv: dict, analysis: JobRequirementsAnalysis, language: str, emphasis: list[str]) -> dict:
    """Rule-based tailoring: reorder experience bullets, tweak summary, inject keywords."""
    import copy
    tailored = copy.deepcopy(cv)

    # Reorder experience to put most relevant first
    exp_scores = {m["index"]: m["relevance_score"] for m in analysis.matching_experience}
    tailored["experience"].sort(key=lambda e: exp_scores.get(cv["experience"].index(e) if e in cv["experience"] else -1, 0), reverse=True)

    # Boost bullets that match required skills
    required_lower = [s.lower() for s in analysis.required_skills]
    for exp in tailored["experience"]:
        bullets = exp.get("bullets", [])
        scored = [(b, sum(1 for sk in required_lower if sk in b.lower())) for b in bullets]
        scored.sort(key=lambda x: x[1], reverse=True)
        exp["bullets"] = [b for b, _ in scored]

    # Tailor summary
    role_keywords = ", ".join(analysis.required_skills[:4]) if analysis.required_skills else job.title
    if language == "pt":
        tailored["summary"] = (
            f"Profissional de estratégia e operações com mais de 10 anos de experiência, "
            f"especializado em {role_keywords}. "
            f"Histórico comprovado de entrega de resultados em ambientes dinâmicos, "
            f"com forte atuação em gestão de portfólio, programas e parcerias institucionais."
        )
    else:
        tailored["summary"] = (
            f"Strategy and operations professional with 10+ years of experience, "
            f"specializing in {role_keywords}. "
            f"Proven track record of delivering results in dynamic environments, "
            f"with strong background in portfolio management, programs, and institutional partnerships."
        )

    cover_letter = _template_cover_letter(job, tailored, analysis, language)

    return {
        "resume_data": tailored,
        "cover_letter": cover_letter,
        "model_used": "template",
        "cost_usd": 0.0,
        "notes": {
            "reordered_experience": len(analysis.matching_experience),
            "matched_skills": analysis.required_skills[:6],
            "skill_gaps": analysis.skill_gaps,
        },
    }


def _template_cover_letter(job: Job, cv: dict, analysis: JobRequirementsAnalysis, language: str) -> str:
    name = cv.get("full_name") or "Candidate"
    email = cv.get("email") or ""
    linkedin = cv.get("linkedin") or ""
    current = cv["experience"][0] if cv.get("experience") else {}
    matched = ", ".join(analysis.required_skills[:3]) if analysis.required_skills else "strategy and operations"

    # Pull a usable lead-bullet, falling back to a generic phrase if the CV
    # has no experience or that role has no bullets parsed yet (heuristic
    # imports often produce bullet-less entries until the user edits them).
    bullets = current.get("bullets") if isinstance(current.get("bullets"), list) else []
    if language == "pt":
        lead_bullet = bullets[0] if bullets else "atuo na gestão de programas e parcerias estratégicas"
    else:
        lead_bullet = bullets[0] if bullets else "lead programs and strategic partnerships"
    lead_bullet = (lead_bullet or "").strip()
    if lead_bullet:
        # Lowercase the first character only — keep proper nouns intact.
        lead_bullet = lead_bullet[0].lower() + lead_bullet[1:]

    if language == "pt":
        current_title = current.get("title") or "Analista"
        current_company = current.get("company") or "minha posição atual"
        return f"""Prezado(a) Time de Recrutamento da {job.company},

Escrevo para manifestar meu interesse na vaga de {job.title}. Com mais de uma década de experiência em estratégia, operações e gestão, estou confiante de que meu perfil se alinha ao que vocês buscam.

Atualmente sou {current_title} na {current_company}, onde {lead_bullet}. Minha experiência abrange especialmente as áreas de {matched}, que identifico como centrais para esta posição.

O que me atrai na {job.company} é a oportunidade de contribuir em um ambiente dinâmico e orientado a resultados. Estou animado com a possibilidade de aplicar minha experiência em gestão de programas, análise estratégica e construção de parcerias para agregar valor à equipe.

Ficaria feliz em conversar sobre como posso contribuir para os objetivos da {job.company}.

Atenciosamente,
{name}
{email} | {linkedin}"""
    else:
        current_title = current.get("title") or "Analyst"
        current_company = current.get("company") or "my current role"
        return f"""Dear Hiring Team at {job.company},

I am writing to express my strong interest in the {job.title} position. With over a decade of experience in strategy, operations, and management, I am confident that my background aligns well with what you are looking for.

Currently serving as {current_title} at {current_company}, I {lead_bullet}. My experience spans particularly in {matched}, which I identify as central to this role.

What draws me to {job.company} is the opportunity to contribute in a dynamic, results-oriented environment. I am excited about the prospect of applying my expertise in program management, strategic analysis, and partnership building to add value to your team.

I would welcome the opportunity to discuss how my experience can contribute to {job.company}'s goals.

Best regards,
{name}
{email} | {linkedin}"""


async def _ollama_tailor(job, cv, analysis, language, emphasis, model, custom_instructions) -> dict:
    prompt = _build_prompt(job, cv, analysis, language, emphasis, custom_instructions)

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data.get("response", "")
    except httpx.ConnectError:
        raise TailoringError("Cannot connect to Ollama. Make sure Ollama is running on localhost:11434.")

    return _parse_llm_response(raw_text, job, cv, analysis, language, f"ollama:{model}")


async def _openai_tailor(job, cv, analysis, language, emphasis, model, custom_instructions) -> dict:
    api_key = settings_store.get("openai_api_key")
    if not api_key:
        raise TailoringError("OpenAI API key not configured. Set it in Settings → AI Provider.")

    prompt = _build_prompt(job, cv, analysis, language, emphasis, custom_instructions)
    cost = estimate_cost("openai", model, job.description, cv)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 3000},
        )
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]

    result = _parse_llm_response(raw_text, job, cv, analysis, language, f"openai:{model}")
    result["cost_usd"] = cost.estimated_cost_usd
    return result


async def _anthropic_tailor(job, cv, analysis, language, emphasis, model, custom_instructions) -> dict:
    api_key = settings_store.get("anthropic_api_key")
    if not api_key:
        raise TailoringError("Anthropic API key not configured. Set it in Settings → AI Provider.")

    prompt = _build_prompt(job, cv, analysis, language, emphasis, custom_instructions)
    cost = estimate_cost("anthropic", model, job.description, cv)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={"model": model, "max_tokens": 3000, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["content"][0]["text"]

    result = _parse_llm_response(raw_text, job, cv, analysis, language, f"anthropic:{model}")
    result["cost_usd"] = cost.estimated_cost_usd
    return result


def _build_prompt(job: Job, cv: dict, analysis: JobRequirementsAnalysis, language: str, emphasis: list[str], custom_instructions: str) -> str:
    lang_instruction = "Respond in Portuguese (Brazil)." if language == "pt" else "Respond in English."
    return f"""You are an expert career coach and resume writer. Your task is to tailor a resume and write a cover letter for a specific job application.

{lang_instruction}

## Job Details
Company: {job.company}
Title: {job.title}
Location: {job.location}

## Job Description (excerpt)
{job.description[:2000]}

## Required Skills Identified
{', '.join(analysis.required_skills)}

## Candidate's Current CV (JSON)
{json.dumps(cv, ensure_ascii=False, indent=2)[:3000]}

## Instructions
1. Rewrite the CV summary to specifically target this role. Keep it to 2-3 sentences.
2. Reorder the experience bullets within each role to put the most relevant ones first.
3. Add or emphasize keywords from the job description naturally in bullet points.
4. Write a compelling cover letter (3-4 paragraphs) that connects the candidate's experience to this specific role.
5. Do NOT fabricate experience or skills the candidate doesn't have.
{f'6. Specifically emphasize: {", ".join(emphasis)}' if emphasis else ''}
{f'7. {custom_instructions}' if custom_instructions else ''}

## Output Format (JSON)
Return a JSON object with exactly these keys:
{{
  "tailored_summary": "...",
  "tailored_experience": [
    {{"company": "...", "title": "...", "bullets": ["...", "..."]}}
  ],
  "cover_letter": "..."
}}
Only return the JSON, no other text."""


def _parse_llm_response(raw_text: str, job: Job, cv: dict, analysis: JobRequirementsAnalysis, language: str, model_used: str) -> dict:
    import copy
    tailored = copy.deepcopy(cv)

    json_match = re.search(r'\{[\s\S]*\}', raw_text)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            if "tailored_summary" in parsed:
                tailored["summary"] = parsed["tailored_summary"]
            if "tailored_experience" in parsed:
                exp_map = {e["company"]: e for e in parsed["tailored_experience"]}
                for exp in tailored["experience"]:
                    if exp["company"] in exp_map:
                        exp["bullets"] = exp_map[exp["company"]].get("bullets", exp["bullets"])
            cover_letter = parsed.get("cover_letter", "")
        except json.JSONDecodeError:
            cover_letter = raw_text
    else:
        cover_letter = raw_text

    if not cover_letter:
        cover_letter = _template_cover_letter(job, tailored, analysis, language)

    return {
        "resume_data": tailored,
        "cover_letter": cover_letter,
        "model_used": model_used,
        "cost_usd": 0.0,
        "notes": {
            "matched_skills": analysis.required_skills[:6],
            "skill_gaps": analysis.skill_gaps,
        },
    }
