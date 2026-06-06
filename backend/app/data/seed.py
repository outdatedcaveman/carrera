"""Seed the database with Bruno's default data on first run."""
import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from ..models import BaseResume, SearchProfile, Source, ApplicationTemplate


DATA_DIR = Path(__file__).parent


def seed_base_resumes(db: Session) -> None:
    if db.query(BaseResume).count() > 0:
        return

    # Check for personal CV files first (local dev environment), fall back to public resume templates
    for lang, filenames in [("en", ["bruno_cv_en.json", "resume_en.json"]), 
                             ("pt", ["bruno_cv_pt.json", "resume_pt.json"])]:
        data = None
        loaded_filename = None
        for filename in filenames:
            cv_path = DATA_DIR / filename
            if cv_path.exists():
                try:
                    with open(cv_path, encoding="utf-8") as f:
                        data = json.load(f)
                    loaded_filename = filename
                    break
                except Exception:
                    pass
        if not data:
            continue
            
        first_name = data.get("full_name", "Candidate").split()[0]
        resume = BaseResume(
            name=f"{first_name} - {'English' if lang == 'en' else 'Português'}",
            language=lang,
            is_default=(lang == "en"),
            data=data,
            version=1,
        )
        db.add(resume)
    db.commit()


def seed_default_profile(db: Session) -> None:
    if db.query(SearchProfile).count() > 0:
        return

    # Try to find user's name from base resume or use Candidate
    default_name = "Candidate"
    en_resume = db.query(BaseResume).filter(BaseResume.language == "en", BaseResume.is_default == True).first()
    if en_resume and en_resume.data:
        default_name = en_resume.data.get("full_name", "Candidate").split()[0]

    profile = SearchProfile(
        name=f"{default_name} - Brazil + Remote",
        enabled=True,
        config={
            "titles": [
                "Analista de Gestão",
                "Business Analyst",
                "Product Manager",
                "Program Manager",
                "Strategy Analyst",
                "Innovation Manager",
                "Project Manager",
                "Portfolio Analyst",
                "Operations Manager",
                "Gerente de Projetos",
                "Analista de Negócios",
                "Analista de Estratégia",
            ],
            "locations": [
                "São Paulo",
                "Remote",
                "Rio de Janeiro",
                "Florianópolis",
                "Curitiba",
                "Belo Horizonte",
                "Porto Alegre",
                "Brasília",
                "Salvador",
            ],
            "salary_min_brl": 8000,
            "salary_max_brl": None,
            "salary_min_usd": None,
            "salary_max_usd": None,
            "remote_preference": "any",
            "required_keywords": [],
            "preferred_keywords": [
                "inovação", "innovation", "estratégia", "strategy",
                "gestão de projetos", "project management",
                "portfólio", "portfolio", "real estate",
                "empreendedorismo", "entrepreneurship",
                "educação", "education", "impacto", "impact",
            ],
            "excluded_keywords": ["estágio", "intern", "junior", "jr."],
            "excluded_companies": [],
            "scoring_weights": {
                "title": 0.35,
                "location": 0.20,
                "salary": 0.15,
                "skills": 0.20,
                "seniority": 0.10,
            },
        },
    )
    db.add(profile)
    db.commit()


def seed_default_sources(db: Session) -> None:
    if db.query(Source).count() > 0:
        return

    sources = [
        {
            "name": "LinkedIn - Brazil Jobs",
            "type": "linkedin",
            "config": {
                "search_query": "analista gestor gerente estrategia inovacao",
                "location": "Brazil",
                "filters": {"experience_level": ["mid-senior", "director"], "job_type": ["full-time"]},
            },
        },
        {
            "name": "Gupy - São Paulo",
            "type": "gupy",
            "config": {
                "search_query": "analista gestor estrategia",
                "city": "São Paulo",
                "state": "SP",
            },
        },
        {
            "name": "Indeed Brasil",
            "type": "indeed",
            "config": {
                "query": "analista gestor estrategia inovacao",
                "location": "São Paulo, SP",
                "language": "pt",
            },
        },
        {
            "name": "RemoteOK - Business/Management",
            "type": "remoteok",
            "config": {
                "tags": ["business", "management", "strategy", "operations"],
            },
        },
        {
            "name": "WeWorkRemotely - Business & Management",
            "type": "weworkremotely",
            "config": {
                "category": "business-management",
            },
        },
    ]

    for s in sources:
        db.add(Source(**s))
    db.commit()


def seed_cover_letter_templates(db: Session) -> None:
    if db.query(ApplicationTemplate).count() > 0:
        return

    # Try to get seeded user's details for letter signature
    name = "Your Name"
    email = "your.email@example.com"
    linkedin = "linkedin.com/in/yourprofile"
    
    en_resume = db.query(BaseResume).filter(BaseResume.language == "en", BaseResume.is_default == True).first()
    if en_resume and en_resume.data:
        name = en_resume.data.get("full_name", name)
        email = en_resume.data.get("email", email)
        linkedin = en_resume.data.get("linkedin", linkedin)

    templates = [
        {
            "name": "Professional - English",
            "type": "cover_letter",
            "language": "en",
            "is_default": True,
            "content": f"""Dear Hiring Team,

I am writing to express my strong interest in the {{{{ job_title }}}} position at {{{{ company }}}}. With over a decade of experience in strategy, operations, and program management, I am confident that my background aligns well with what you are looking for.

In my current role as Portfolio Management Analyst at Yuca, I {{{{ current_role_highlight }}}}. Prior to this, {{{{ past_role_highlight }}}}.

What particularly excites me about {{{{ company }}}} is {{{{ company_appeal }}}}. I am drawn to this role because {{{{ role_appeal }}}}.

My key strengths that directly apply to this position include:
{{{{ key_strengths }}}}

I would welcome the opportunity to discuss how my experience can contribute to {{{{ company }}}}'s goals. Thank you for your consideration.

Best regards,
{name}
{email}
{linkedin}""",
        },
        {
            "name": "Profissional - Português",
            "type": "cover_letter",
            "language": "pt",
            "is_default": True,
            "content": f"""Prezado(a) Time de Recrutamento,

Escrevo para manifestar meu interesse na vaga de {{{{ job_title }}}} na {{{{ company }}}}. Com mais de uma década de experiência em estratégia, operações e gestão de programas, estou confiante de que meu histórico se alinha ao que vocês buscam.

Em minha função atual como Analista de Gestão de Portfólio na Yuca, {{{{ current_role_highlight }}}}. Anteriormente, {{{{ past_role_highlight }}}}.

O que me atrai particularmente na {{{{ company }}}} é {{{{ company_appeal }}}}. Tenho interesse nesta vaga porque {{{{ role_appeal }}}}.

Minhas principais competências que se aplicam diretamente a esta posição incluem:
{{{{ key_strengths }}}}

Ficaria feliz em conversar sobre como minha experiência pode contribuir para os objetivos da {{{{ company }}}}. Agradeço sua consideração.

Atenciosamente,
{name}
{email}
{linkedin}""",
        },
    ]

    for t in templates:
        db.add(ApplicationTemplate(**t))
    db.commit()


def run_all_seeds(db: Session) -> None:
    seed_base_resumes(db)
    seed_default_profile(db)
    seed_default_sources(db)
    seed_cover_letter_templates(db)
