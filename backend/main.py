import os
import json
import random
import re
import subprocess
import tempfile
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
    Header,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from supabase import create_client, Client


# =========================================================
# UMGEBUNG
# =========================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    "ffmpeg",
)

FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://127.0.0.1:5500",
)

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL fehlt.")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY fehlt."
    )

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY fehlt.")

if (
    FFMPEG_PATH != "ffmpeg"
    and not os.path.exists(FFMPEG_PATH)
):
    raise RuntimeError(
        f"FFmpeg wurde nicht gefunden: {FFMPEG_PATH}"
    )


# =========================================================
# CLIENTS
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Papa erzählt API"
)

allowed_origins = list(
    {
        FRONTEND_ORIGIN,
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# MODELLE
# =========================================================

class AnswerCreate(BaseModel):
    history_id: str
    text: str


class FreeAnswerCreate(BaseModel):
    profile_id: str


class FollowUpCreate(BaseModel):
    profile_id: str
    parent_answer_id: str
    text: str


class VisibilityUpdate(BaseModel):
    visibility: str


class DiscardAnswerRequest(BaseModel):
    history_id: str | None = None


class TimelineUpdate(BaseModel):
    timeline_year: int | None = None
    timeline_label: str | None = None
    timeline_confidence: str | None = None


class TranscriptUpdate(BaseModel):
    text: str
    change_note: str | None = None


class SupplementCreate(BaseModel):
    transcript: str
    supplement_type: str = "clarification"


class IdentityResolution(BaseModel):
    same_person: bool


# =========================================================
# ALLGEMEINE HILFSFUNKTIONEN
# =========================================================

def utc_now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def parse_json_response(raw_text: str):
    text = clean_text(raw_text)

    if not text:
        raise ValueError(
            "Leere KI-Antwort."
        )

    if text.startswith("```"):
        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

    return json.loads(text)


def normalize_name(value: str | None):
    text = clean_text(value).lower()

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = re.sub(
        r"[^a-z0-9äöüß]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_confidence(value):
    value = clean_text(value).lower()

    if value in (
        "high",
        "medium",
        "low",
    ):
        return value

    return "medium"


def normalize_identity_status(value):
    value = clean_text(value).lower()

    if value in (
        "unconfirmed",
        "probable",
        "confirmed",
    ):
        return value

    return "unconfirmed"


def normalize_timeline(
    year,
    label,
    confidence,
):
    if not isinstance(year, int):
        year = None

    if (
        year is not None
        and (
            year < 1800
            or year > 2100
        )
    ):
        year = None

    label = clean_text(label)

    confidence = (
        clean_text(confidence)
        or "unknown"
    )

    if confidence not in (
        "exact",
        "approximate",
        "unknown",
    ):
        confidence = "unknown"

    if year is None:
        confidence = "unknown"

    return (
        year,
        label,
        confidence,
    )


def safe_int(value):
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        value = value.strip()

        if value.isdigit():
            return int(value)

    return None


def valid_year(value):
    value = safe_int(value)

    if (
        value is not None
        and 1800 <= value <= 2100
    ):
        return value

    return None


def effective_transcript(answer: dict):
    edited = clean_text(
        answer.get("edited_transcript")
    )

    if edited:
        return edited

    return clean_text(
        answer.get("original_transcript")
    )


# =========================================================
# AUTH
# =========================================================

def get_current_app_user(
    authorization: str | None = Header(
        default=None
    )
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Nicht angemeldet.",
        )

    parts = authorization.split(
        " ",
        1,
    )

    if (
        len(parts) != 2
        or parts[0].lower() != "bearer"
    ):
        raise HTTPException(
            status_code=401,
            detail="Ungültiger Authorization-Header.",
        )

    token = parts[1].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Leerer Login-Token.",
        )

    try:
        auth_response = (
            supabase.auth.get_user(token)
        )
        auth_user = auth_response.user

    except Exception as exc:
        print("AUTH ERROR:", exc)

        raise HTTPException(
            status_code=401,
            detail=(
                "Session ist ungültig "
                "oder abgelaufen."
            ),
        )

    if not auth_user:
        raise HTTPException(
            status_code=401,
            detail=(
                "Benutzer konnte nicht "
                "ermittelt werden."
            ),
        )

    result = (
        supabase
        .table("app_users")
        .select(
            "id, auth_user_id, "
            "display_name, role, profile_id"
        )
        .eq(
            "auth_user_id",
            str(auth_user.id),
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=403,
            detail=(
                "Dieser Benutzer ist nicht "
                "für die App freigeschaltet."
            ),
        )

    app_user = result.data[0]

    app_user["email"] = getattr(
        auth_user,
        "email",
        None,
    )

    return app_user


def require_writer(current_user):
    if current_user["role"] not in (
        "admin",
        "narrator",
    ):
        raise HTTPException(
            status_code=403,
            detail="Keine Schreibberechtigung.",
        )


def authorize_profile(
    current_user,
    profile_id: str,
):
    require_writer(current_user)

    if current_user["role"] == "admin":
        return

    own_profile_id = current_user.get(
        "profile_id"
    )

    if (
        not own_profile_id
        or str(own_profile_id)
        != str(profile_id)
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Dieses Profil gehört nicht "
                "zum angemeldeten Benutzer."
            ),
        )


def authorize_read_profile(
    current_user,
    profile_id: str,
):
    role = current_user["role"]

    if role in (
        "admin",
        "reader",
    ):
        return

    if role == "narrator":
        own_profile_id = current_user.get(
            "profile_id"
        )

        if (
            own_profile_id
            and str(own_profile_id)
            == str(profile_id)
        ):
            return

    raise HTTPException(
        status_code=403,
        detail="Keine Leseberechtigung.",
    )


# =========================================================
# BASIS-DATENBANKHILFEN
# =========================================================

def get_answer_or_404(answer_id: str):
    result = (
        supabase
        .table("answers")
        .select("*")
        .eq("id", answer_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Antwort nicht gefunden.",
        )

    return result.data[0]


def get_history_or_404(history_id: str):
    result = (
        supabase
        .table("question_history")
        .select("*")
        .eq("id", history_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Fragenverlauf nicht gefunden.",
        )

    return result.data[0]


def get_question_or_none(
    question_id: str | None
):
    if not question_id:
        return None

    result = (
        supabase
        .table("questions")
        .select(
            "id, text, category, "
            "source, parent_answer_id"
        )
        .eq("id", question_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def get_person_or_404(person_id: str):
    result = (
        supabase
        .table("people")
        .select("*")
        .eq("id", person_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Person nicht gefunden.",
        )

    return result.data[0]


def get_candidate_or_404(
    candidate_id: str
):
    result = (
        supabase
        .table(
            "person_identity_candidates"
        )
        .select("*")
        .eq("id", candidate_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=(
                "Identitätskandidat "
                "nicht gefunden."
            ),
        )

    return result.data[0]


# =========================================================
# ERINNERUNGSKETTE
# =========================================================

def get_answer_chain(answer: dict):
    chain = []
    current = answer
    visited = set()

    while current:
        current_id = str(
            current.get("id")
        )

        if current_id in visited:
            break

        visited.add(current_id)
        chain.append(current)

        question = get_question_or_none(
            current.get("question_id")
        )

        if not question:
            break

        parent_answer_id = question.get(
            "parent_answer_id"
        )

        if not parent_answer_id:
            break

        parent_result = (
            supabase
            .table("answers")
            .select("*")
            .eq(
                "id",
                parent_answer_id,
            )
            .limit(1)
            .execute()
        )

        if not parent_result.data:
            break

        current = parent_result.data[0]

    chain.reverse()

    return chain


def get_root_answer(answer: dict):
    chain = get_answer_chain(answer)

    if not chain:
        return answer

    return chain[0]


def get_timeline_family_answer_ids(
    root_answer_id: str,
):
    collected = []
    queue = [root_answer_id]
    seen = set()

    while queue:
        parent_answer_id = queue.pop(0)

        if parent_answer_id in seen:
            continue

        seen.add(parent_answer_id)
        collected.append(parent_answer_id)

        child_questions_result = (
            supabase
            .table("questions")
            .select("id")
            .eq(
                "parent_answer_id",
                parent_answer_id,
            )
            .execute()
        )

        child_question_ids = [
            row["id"]
            for row in (
                child_questions_result.data
                or []
            )
            if row.get("id")
        ]

        if not child_question_ids:
            continue

        child_answers_result = (
            supabase
            .table("answers")
            .select("id")
            .in_(
                "question_id",
                child_question_ids,
            )
            .execute()
        )

        for row in (
            child_answers_result.data
            or []
        ):
            child_answer_id = row.get(
                "id"
            )

            if (
                child_answer_id
                and child_answer_id
                not in seen
            ):
                queue.append(
                    child_answer_id
                )

    return collected


def update_timeline_family(
    answer: dict,
    timeline_year: int | None,
    timeline_label: str | None,
    timeline_confidence: str,
):
    root_answer = get_root_answer(
        answer
    )

    family_ids = (
        get_timeline_family_answer_ids(
            root_answer["id"]
        )
    )

    update_data = {
        "timeline_year":
            timeline_year,
        "timeline_label":
            timeline_label,
        "timeline_confidence":
            timeline_confidence,
    }

    if family_ids:
        (
            supabase
            .table("answers")
            .update(update_data)
            .in_("id", family_ids)
            .execute()
        )

    return {
        "root_answer_id":
            root_answer["id"],
        "answer_ids":
            family_ids,
        "timeline":
            update_data,
    }


def get_inherited_timeline_for_question(
    question_id: str | None,
):
    question = get_question_or_none(
        question_id
    )

    if not question:
        return None

    parent_answer_id = question.get(
        "parent_answer_id"
    )

    if not parent_answer_id:
        return None

    parent_answer = get_answer_or_404(
        parent_answer_id
    )

    root_answer = get_root_answer(
        parent_answer
    )

    return {
        "timeline_year":
            root_answer.get(
                "timeline_year"
            ),
        "timeline_label":
            root_answer.get(
                "timeline_label"
            ),
        "timeline_confidence":
            root_answer.get(
                "timeline_confidence"
            )
            or "unknown",
        "root_answer_id":
            root_answer["id"],
    }


# =========================================================
# TRANSKRIPT-VERSIONEN UND ERGÄNZUNGEN
# =========================================================

def ensure_original_revision(
    answer_id: str,
    transcript: str,
):
    existing = (
        supabase
        .table(
            "answer_transcript_revisions"
        )
        .select("id")
        .eq(
            "answer_id",
            answer_id,
        )
        .eq(
            "version_number",
            1,
        )
        .limit(1)
        .execute()
    )

    if existing.data:
        (
            supabase
            .table(
                "answer_transcript_revisions"
            )
            .update(
                {
                    "transcript":
                        transcript,
                    "change_type":
                        "original",
                }
            )
            .eq(
                "id",
                existing.data[0]["id"],
            )
            .execute()
        )
        return

    (
        supabase
        .table(
            "answer_transcript_revisions"
        )
        .insert(
            {
                "answer_id":
                    answer_id,
                "version_number":
                    1,
                "transcript":
                    transcript,
                "change_type":
                    "original",
                "change_note":
                    "Ursprüngliche Transkription",
            }
        )
        .execute()
    )


def get_supplements(answer_id: str):
    result = (
        supabase
        .table("answer_supplements")
        .select("*")
        .eq(
            "answer_id",
            answer_id,
        )
        .order(
            "created_at",
        )
        .execute()
    )

    return result.data or []


def get_effective_answer_text(
    answer: dict,
    include_supplements=True,
):
    text = effective_transcript(
        answer
    )

    if not include_supplements:
        return text

    supplements = get_supplements(
        answer["id"]
    )

    supplement_texts = []

    for supplement in supplements:
        value = clean_text(
            supplement.get("transcript")
        )

        if value:
            supplement_texts.append(
                value
            )

    if supplement_texts:
        return (
            text
            + "\n\nErgänzungen / Präzisierungen:\n"
            + "\n".join(
                f"- {value}"
                for value
                in supplement_texts
            )
        ).strip()

    return text


def build_full_memory_context(
    answer: dict
):
    chain = get_answer_chain(
        answer
    )

    sections = []

    for index, chain_answer in enumerate(
        chain,
        start=1,
    ):
        question = get_question_or_none(
            chain_answer.get(
                "question_id"
            )
        )

        text = get_effective_answer_text(
            chain_answer,
            include_supplements=True,
        )

        if question:
            section = (
                f"ABSCHNITT {index}\n"
                f"Frage: "
                f"{clean_text(question.get('text'))}\n"
                f"Antwort: {text}"
            )
        else:
            section = (
                f"ABSCHNITT {index}\n"
                f"Freie Erzählung: {text}"
            )

        sections.append(section)

    return "\n\n".join(sections)


# =========================================================
# BEKANNTE PERSONEN
# =========================================================

def get_known_people(
    profile_id: str,
):
    people_result = (
        supabase
        .table("people")
        .select("*")
        .eq(
            "profile_id",
            profile_id,
        )
        .is_(
            "merged_into_person_id",
            "null",
        )
        .order(
            "created_at",
        )
        .execute()
    )

    people = people_result.data or []

    if not people:
        return []

    person_ids = [
        person["id"]
        for person in people
    ]

    aliases_result = (
        supabase
        .table("person_aliases")
        .select("*")
        .in_(
            "person_id",
            person_ids,
        )
        .execute()
    )

    relationships_result = (
        supabase
        .table(
            "person_narrator_relationships"
        )
        .select("*")
        .in_(
            "person_id",
            person_ids,
        )
        .neq(
            "status",
            "rejected",
        )
        .execute()
    )

    facts_result = (
        supabase
        .table("person_facts")
        .select("*")
        .in_(
            "person_id",
            person_ids,
        )
        .neq(
            "status",
            "rejected",
        )
        .execute()
    )

    alias_map = {}
    relationship_map = {}
    fact_map = {}

    for row in (
        aliases_result.data
        or []
    ):
        alias_map.setdefault(
            row["person_id"],
            [],
        ).append(
            row.get("alias")
        )

    for row in (
        relationships_result.data
        or []
    ):
        relationship_map.setdefault(
            row["person_id"],
            [],
        ).append(
            row
        )

    for row in (
        facts_result.data
        or []
    ):
        fact_map.setdefault(
            row["person_id"],
            [],
        ).append(
            row
        )

    result = []

    for person in people:
        result.append(
            {
                "id":
                    person["id"],
                "name":
                    person.get(
                        "canonical_name"
                    ),
                "description":
                    person.get(
                        "description"
                    ),
                "relationship_summary":
                    person.get(
                        "relationship_to_narrator"
                    ),
                "birth_year":
                    person.get(
                        "birth_year"
                    ),
                "death_year":
                    person.get(
                        "death_year"
                    ),
                "identity_status":
                    person.get(
                        "identity_status"
                    ),
                "aliases":
                    [
                        value
                        for value
                        in alias_map.get(
                            person["id"],
                            [],
                        )
                        if value
                    ],
                "relationships":
                    relationship_map.get(
                        person["id"],
                        [],
                    ),
                "facts":
                    fact_map.get(
                        person["id"],
                        [],
                    ),
            }
        )

    return result


def compact_known_people_for_ai(
    people: list,
):
    compact = []

    for person in people:
        relationships = []

        for relation in person.get(
            "relationships",
            []
        ):
            relationships.append(
                {
                    "relationship_type":
                        relation.get(
                            "relationship_type"
                        ),
                    "description":
                        relation.get(
                            "description"
                        ),
                    "status":
                        relation.get(
                            "status"
                        ),
                }
            )

        facts = []

        for fact in person.get(
            "facts",
            []
        )[:8]:
            facts.append(
                {
                    "type":
                        fact.get(
                            "fact_type"
                        ),
                    "value":
                        fact.get(
                            "fact_value"
                        ),
                    "status":
                        fact.get(
                            "status"
                        ),
                }
            )

        compact.append(
            {
                "person_id":
                    person["id"],
                "name":
                    person.get("name"),
                "aliases":
                    person.get(
                        "aliases",
                        [],
                    ),
                "relationship_summary":
                    person.get(
                        "relationship_summary"
                    ),
                "relationships":
                    relationships,
                "facts":
                    facts,
            }
        )

    return compact


def find_name_candidate(
    known_people: list,
    mentioned_name: str,
):
    normalized = normalize_name(
        mentioned_name
    )

    if not normalized:
        return None

    matches = []

    for person in known_people:
        names = [
            person.get("name"),
            *person.get(
                "aliases",
                [],
            ),
        ]

        normalized_names = {
            normalize_name(name)
            for name in names
            if clean_text(name)
        }

        if normalized in normalized_names:
            matches.append(person)

    if len(matches) == 1:
        return matches[0]

    return None


# =========================================================
# PERSONEN SPEICHERN
# =========================================================

def create_provisional_person(
    profile_id: str,
    person_data: dict,
):
    canonical_name = (
        clean_text(
            person_data.get("name")
        )
        or clean_text(
            person_data.get(
                "mentioned_as"
            )
        )
        or "Unbekannte Person"
    )

    birth_year = valid_year(
        person_data.get(
            "birth_year"
        )
    )

    death_year = valid_year(
        person_data.get(
            "death_year"
        )
    )

    result = (
        supabase
        .table("people")
        .insert(
            {
                "profile_id":
                    profile_id,
                "canonical_name":
                    canonical_name,
                "normalized_name":
                    normalize_name(
                        canonical_name
                    ),
                "relationship_to_narrator":
                    clean_text(
                        person_data.get(
                            "relationship_to_narrator"
                        )
                    )
                    or None,
                "description":
                    clean_text(
                        person_data.get(
                            "description"
                        )
                    )
                    or None,
                "birth_year":
                    birth_year,
                "death_year":
                    death_year,
                "identity_status":
                    "provisional",
            }
        )
        .execute()
    )

    return result.data[0]


def add_alias_if_missing(
    person_id: str,
    alias: str,
):
    alias = clean_text(alias)

    if not alias:
        return

    normalized = normalize_name(
        alias
    )

    existing = (
        supabase
        .table("person_aliases")
        .select("id")
        .eq(
            "person_id",
            person_id,
        )
        .eq(
            "normalized_alias",
            normalized,
        )
        .limit(1)
        .execute()
    )

    if existing.data:
        return

    (
        supabase
        .table("person_aliases")
        .insert(
            {
                "person_id":
                    person_id,
                "alias":
                    alias,
                "normalized_alias":
                    normalized,
            }
        )
        .execute()
    )


def link_person_to_answer(
    answer_id: str,
    person_id: str,
    mentioned_as: str,
    context: str,
    confidence: str,
    role_in_memory: str,
    identification_status: str,
):
    existing = (
        supabase
        .table("answer_people")
        .select("id")
        .eq(
            "answer_id",
            answer_id,
        )
        .eq(
            "person_id",
            person_id,
        )
        .limit(1)
        .execute()
    )

    payload = {
        "mentioned_as":
            clean_text(
                mentioned_as
            )
            or None,
        "context":
            clean_text(
                context
            )
            or None,
        "confidence":
            normalize_confidence(
                confidence
            ),
        "role_in_memory":
            clean_text(
                role_in_memory
            )
            or None,
        "identification_status":
            normalize_identity_status(
                identification_status
            ),
    }

    if existing.data:
        (
            supabase
            .table("answer_people")
            .update(payload)
            .eq(
                "id",
                existing.data[0]["id"],
            )
            .execute()
        )
        return

    payload["answer_id"] = answer_id
    payload["person_id"] = person_id

    (
        supabase
        .table("answer_people")
        .insert(payload)
        .execute()
    )


def add_narrator_relationship(
    profile_id: str,
    person_id: str,
    answer_id: str,
    relationship_type: str,
    description: str | None,
    start_year,
    end_year,
    confidence="medium",
    status="inferred",
):
    relationship_type = clean_text(
        relationship_type
    )

    if not relationship_type:
        return

    existing = (
        supabase
        .table(
            "person_narrator_relationships"
        )
        .select("id, status")
        .eq(
            "profile_id",
            profile_id,
        )
        .eq(
            "person_id",
            person_id,
        )
        .eq(
            "relationship_type",
            relationship_type,
        )
        .neq(
            "status",
            "rejected",
        )
        .limit(1)
        .execute()
    )

    if existing.data:
        return

    (
        supabase
        .table(
            "person_narrator_relationships"
        )
        .insert(
            {
                "profile_id":
                    profile_id,
                "person_id":
                    person_id,
                "relationship_type":
                    relationship_type,
                "description":
                    clean_text(
                        description
                    )
                    or None,
                "start_year":
                    valid_year(
                        start_year
                    ),
                "end_year":
                    valid_year(
                        end_year
                    ),
                "source_answer_id":
                    answer_id,
                "confidence":
                    normalize_confidence(
                        confidence
                    ),
                "status":
                    status,
            }
        )
        .execute()
    )

    person = get_person_or_404(
        person_id
    )

    if not clean_text(
        person.get(
            "relationship_to_narrator"
        )
    ):
        (
            supabase
            .table("people")
            .update(
                {
                    "relationship_to_narrator":
                        relationship_type,
                    "updated_at":
                        utc_now_iso(),
                }
            )
            .eq(
                "id",
                person_id,
            )
            .execute()
        )


def add_person_fact(
    profile_id: str,
    person_id: str,
    answer_id: str,
    fact_type: str,
    fact_value: str,
    confidence="medium",
    status="inferred",
):
    fact_type = clean_text(
        fact_type
    )
    fact_value = clean_text(
        fact_value
    )

    if (
        not fact_type
        or not fact_value
    ):
        return

    existing = (
        supabase
        .table("person_facts")
        .select("id")
        .eq(
            "profile_id",
            profile_id,
        )
        .eq(
            "person_id",
            person_id,
        )
        .eq(
            "fact_type",
            fact_type,
        )
        .eq(
            "fact_value",
            fact_value,
        )
        .neq(
            "status",
            "rejected",
        )
        .limit(1)
        .execute()
    )

    if existing.data:
        return

    (
        supabase
        .table("person_facts")
        .insert(
            {
                "profile_id":
                    profile_id,
                "person_id":
                    person_id,
                "fact_type":
                    fact_type,
                "fact_value":
                    fact_value,
                "source_answer_id":
                    answer_id,
                "confidence":
                    normalize_confidence(
                        confidence
                    ),
                "status":
                    status,
            }
        )
        .execute()
    )


def create_identity_candidate(
    profile_id: str,
    answer_id: str,
    source_person_id: str,
    candidate_person_id: str,
    mentioned_name: str,
    confidence_score,
    reason: str,
    clarification_question: str,
):
    if (
        str(source_person_id)
        == str(candidate_person_id)
    ):
        return None

    existing = (
        supabase
        .table(
            "person_identity_candidates"
        )
        .select("*")
        .eq(
            "answer_id",
            answer_id,
        )
        .eq(
            "source_person_id",
            source_person_id,
        )
        .eq(
            "candidate_person_id",
            candidate_person_id,
        )
        .eq(
            "status",
            "pending",
        )
        .limit(1)
        .execute()
    )

    if existing.data:
        return existing.data[0]

    try:
        score = float(
            confidence_score
        )
    except Exception:
        score = 0.5

    score = max(
        0.0,
        min(
            score,
            1.0,
        ),
    )

    result = (
        supabase
        .table(
            "person_identity_candidates"
        )
        .insert(
            {
                "profile_id":
                    profile_id,
                "answer_id":
                    answer_id,
                "source_person_id":
                    source_person_id,
                "mentioned_name":
                    clean_text(
                        mentioned_name
                    )
                    or None,
                "candidate_person_id":
                    candidate_person_id,
                "confidence_score":
                    score,
                "reason":
                    clean_text(
                        reason
                    )
                    or None,
                "clarification_question":
                    clean_text(
                        clarification_question
                    )
                    or None,
                "status":
                    "pending",
            }
        )
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


# =========================================================
# PERSONEN-MERGE
# =========================================================

def merge_people(
    source_person_id: str,
    target_person_id: str,
    resolved_by: str | None = None,
):
    if (
        str(source_person_id)
        == str(target_person_id)
    ):
        return target_person_id

    source = get_person_or_404(
        source_person_id
    )

    target = get_person_or_404(
        target_person_id
    )

    if (
        str(source["profile_id"])
        != str(target["profile_id"])
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Personen gehören zu "
                "verschiedenen Profilen."
            ),
        )

    # -----------------------------------------------------
    # ANSWER PEOPLE
    # -----------------------------------------------------

    source_links = (
        supabase
        .table("answer_people")
        .select("*")
        .eq(
            "person_id",
            source_person_id,
        )
        .execute()
    )

    for link in (
        source_links.data
        or []
    ):
        existing_target = (
            supabase
            .table("answer_people")
            .select("id")
            .eq(
                "answer_id",
                link["answer_id"],
            )
            .eq(
                "person_id",
                target_person_id,
            )
            .limit(1)
            .execute()
        )

        if existing_target.data:
            (
                supabase
                .table("answer_people")
                .delete()
                .eq(
                    "id",
                    link["id"],
                )
                .execute()
            )
        else:
            (
                supabase
                .table("answer_people")
                .update(
                    {
                        "person_id":
                            target_person_id,
                        "identification_status":
                            "confirmed",
                    }
                )
                .eq(
                    "id",
                    link["id"],
                )
                .execute()
            )

    # -----------------------------------------------------
    # ALIASE
    # -----------------------------------------------------

    source_aliases = (
        supabase
        .table("person_aliases")
        .select("*")
        .eq(
            "person_id",
            source_person_id,
        )
        .execute()
    )

    source_name = clean_text(
        source.get(
            "canonical_name"
        )
    )

    if source_name:
        add_alias_if_missing(
            target_person_id,
            source_name,
        )

    for alias in (
        source_aliases.data
        or []
    ):
        add_alias_if_missing(
            target_person_id,
            alias.get("alias"),
        )

    # -----------------------------------------------------
    # FAKTEN
    # -----------------------------------------------------

    source_facts = (
        supabase
        .table("person_facts")
        .select("*")
        .eq(
            "person_id",
            source_person_id,
        )
        .execute()
    )

    for fact in (
        source_facts.data
        or []
    ):
        existing_fact = (
            supabase
            .table("person_facts")
            .select("id")
            .eq(
                "person_id",
                target_person_id,
            )
            .eq(
                "fact_type",
                fact["fact_type"],
            )
            .eq(
                "fact_value",
                fact["fact_value"],
            )
            .limit(1)
            .execute()
        )

        if existing_fact.data:
            (
                supabase
                .table("person_facts")
                .delete()
                .eq(
                    "id",
                    fact["id"],
                )
                .execute()
            )
        else:
            (
                supabase
                .table("person_facts")
                .update(
                    {
                        "person_id":
                            target_person_id,
                    }
                )
                .eq(
                    "id",
                    fact["id"],
                )
                .execute()
            )

    # -----------------------------------------------------
    # BEZIEHUNGEN ZU ROMAN
    # -----------------------------------------------------

    source_relations = (
        supabase
        .table(
            "person_narrator_relationships"
        )
        .select("*")
        .eq(
            "person_id",
            source_person_id,
        )
        .execute()
    )

    for relation in (
        source_relations.data
        or []
    ):
        existing_relation = (
            supabase
            .table(
                "person_narrator_relationships"
            )
            .select("id")
            .eq(
                "person_id",
                target_person_id,
            )
            .eq(
                "relationship_type",
                relation[
                    "relationship_type"
                ],
            )
            .neq(
                "status",
                "rejected",
            )
            .limit(1)
            .execute()
        )

        if existing_relation.data:
            (
                supabase
                .table(
                    "person_narrator_relationships"
                )
                .delete()
                .eq(
                    "id",
                    relation["id"],
                )
                .execute()
            )
        else:
            (
                supabase
                .table(
                    "person_narrator_relationships"
                )
                .update(
                    {
                        "person_id":
                            target_person_id,
                    }
                )
                .eq(
                    "id",
                    relation["id"],
                )
                .execute()
            )

    # -----------------------------------------------------
    # PERSON ↔ PERSON RELATIONSHIPS
    # -----------------------------------------------------

    (
        supabase
        .table("person_relationships")
        .update(
            {
                "person_a_id":
                    target_person_id,
            }
        )
        .eq(
            "person_a_id",
            source_person_id,
        )
        .execute()
    )

    (
        supabase
        .table("person_relationships")
        .update(
            {
                "person_b_id":
                    target_person_id,
            }
        )
        .eq(
            "person_b_id",
            source_person_id,
        )
        .execute()
    )

    # -----------------------------------------------------
    # QUELLPERSON ALS VERSCHMOLZEN MARKIEREN
    # -----------------------------------------------------

    (
        supabase
        .table("people")
        .update(
            {
                "merged_into_person_id":
                    target_person_id,
                "updated_at":
                    utc_now_iso(),
            }
        )
        .eq(
            "id",
            source_person_id,
        )
        .execute()
    )

    (
        supabase
        .table("people")
        .update(
            {
                "identity_status":
                    "confirmed",
                "updated_at":
                    utc_now_iso(),
            }
        )
        .eq(
            "id",
            target_person_id,
        )
        .execute()
    )

    return target_person_id


def resolve_identity_candidate_internal(
    candidate: dict,
    same_person: bool,
    resolved_by: str | None,
):
    if candidate.get("status") != "pending":
        return candidate

    now = utc_now_iso()

    if same_person:
        source_person_id = candidate.get(
            "source_person_id"
        )
        target_person_id = candidate.get(
            "candidate_person_id"
        )

        if (
            source_person_id
            and target_person_id
        ):
            merge_people(
                source_person_id,
                target_person_id,
                resolved_by,
            )

        status = "confirmed"

    else:
        source_person_id = candidate.get(
            "source_person_id"
        )

        if source_person_id:
            (
                supabase
                .table("people")
                .update(
                    {
                        "identity_status":
                            "confirmed",
                        "updated_at":
                            now,
                    }
                )
                .eq(
                    "id",
                    source_person_id,
                )
                .execute()
            )

        status = "rejected"

    (
        supabase
        .table(
            "person_identity_candidates"
        )
        .update(
            {
                "status":
                    status,
                "resolved_at":
                    now,
                "resolved_by":
                    resolved_by,
            }
        )
        .eq(
            "id",
            candidate["id"],
        )
        .execute()
    )

    return get_candidate_or_404(
        candidate["id"]
    )


# =========================================================
# REANALYSE: ALTE KI-INFERENZEN ENTFERNEN
# =========================================================

def clear_inferred_data_for_answer(
    answer_id: str,
):
    (
        supabase
        .table("person_facts")
        .delete()
        .eq(
            "source_answer_id",
            answer_id,
        )
        .eq(
            "status",
            "inferred",
        )
        .execute()
    )

    (
        supabase
        .table(
            "person_narrator_relationships"
        )
        .delete()
        .eq(
            "source_answer_id",
            answer_id,
        )
        .eq(
            "status",
            "inferred",
        )
        .execute()
    )

    (
        supabase
        .table("person_relationships")
        .delete()
        .eq(
            "source_answer_id",
            answer_id,
        )
        .eq(
            "status",
            "inferred",
        )
        .execute()
    )

    (
        supabase
        .table(
            "person_identity_candidates"
        )
        .delete()
        .eq(
            "answer_id",
            answer_id,
        )
        .eq(
            "status",
            "pending",
        )
        .execute()
    )

    # Nur nicht bestätigte Links entfernen.
    # Menschlich bestätigte Identitäten bleiben erhalten.
    (
        supabase
        .table("answer_people")
        .delete()
        .eq(
            "answer_id",
            answer_id,
        )
        .neq(
            "identification_status",
            "confirmed",
        )
        .execute()
    )


# =========================================================
# KI: ERINNERUNG ANALYSIEREN
# =========================================================

def analyze_memory_with_ai(
    answer: dict,
):
    transcript = get_effective_answer_text(
        answer,
        include_supplements=True,
    )

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail=(
                "Die Antwort enthält "
                "noch kein Transkript."
            ),
        )

    question = get_question_or_none(
        answer.get("question_id")
    )

    question_text = (
        clean_text(
            question.get("text")
        )
        if question
        else ""
    )

    known_people = get_known_people(
        answer["profile_id"]
    )

    known_people_ai = (
        compact_known_people_for_ai(
            known_people
        )
    )

    known_people_json = json.dumps(
        known_people_ai,
        ensure_ascii=False,
    )

    if question_text:
        context_text = (
            "Frage:\n"
            f"{question_text}"
        )
    else:
        context_text = (
            "Es handelt sich um eine "
            "freie Erinnerung."
        )

    prompt = f"""
Du analysierst eine persönliche Lebenserinnerung
für ein privates Familienarchiv.

Erzähler ist Roman.

{context_text}

ERZÄHLUNG:
{transcript}

BEREITS BEKANNTE PERSONEN:
{known_people_json}

WICHTIG:
Die bekannten Personen sind nur mögliche
Identitätskandidaten.

Eine neue Erwähnung darf NICHT einfach mit
einer bekannten Person verschmolzen werden,
wenn die Identität nicht eindeutig aus Romans
Worten hervorgeht.

Antworte ausschließlich mit gültigem JSON.

FORMAT:

{{
  "summary": "",
  "places": [],
  "years": [],
  "topics": [],
  "keywords": [],

  "people": [
    {{
      "mentioned_as": "",
      "name": "",
      "description": "",
      "relationship_to_narrator": "",
      "role_in_memory": "",
      "birth_year": null,
      "death_year": null,
      "aliases": [],
      "facts": [
        {{
          "type": "",
          "value": "",
          "confidence": "medium"
        }}
      ],
      "relationship_start_year": null,
      "relationship_end_year": null,
      "confidence": "medium",

      "candidate_person_id": null,
      "identity_confidence": 0.0,
      "identity_reason": "",
      "needs_identity_clarification": false,
      "clarification_question": ""
    }}
  ],

  "person_relationships": [
    {{
      "person_a_mentioned_as": "",
      "person_b_mentioned_as": "",
      "relationship_type": "",
      "description": "",
      "confidence": "medium"
    }}
  ],

  "privacy_signal": false,
  "privacy_reason": "",

  "timeline_year": null,
  "timeline_label": "",
  "timeline_confidence": "unknown",

  "identity_resolution": {{
    "candidate_id": null,
    "resolution": "none"
  }}
}}

--------------------------------------------------
PERSONEN
--------------------------------------------------

Erfasse JEDE konkrete menschliche Person,
die Roman erwähnt.

Nicht als Person erfassen:
- Roman selbst
- unbestimmte Gruppen wie "die Leute"
- Institutionen
- Firmen
- Länder
- Tiere
- fiktive Figuren, sofern sie nicht als reale
  Beziehungsperson beschrieben werden

Wenn Roman nur sagt:
"meine Mutter"
dann ist name leer oder "Mutter", aber
mentioned_as = "meine Mutter" und
relationship_to_narrator = "Mutter".

Wenn Roman sagt:
"Trini, meine erste Freundin"
dann:
name = "Trini"
relationship_to_narrator = "erste Freundin".

relationship_to_narrator darf nur aus dem
Gesagten folgen. Nichts erfinden.

role_in_memory beschreibt kurz die Rolle der
Person in genau dieser Erinnerung.

facts:
Nur Tatsachen über diese Person, die Roman
tatsächlich erzählt.
Keine Interpretation als Tatsache ausgeben.

--------------------------------------------------
PERSONEN-WIEDERERKENNUNG
--------------------------------------------------

Prüfe, ob eine erwähnte Person möglicherweise
eine Person aus BEREITS BEKANNTE PERSONEN ist.

Wenn es eine plausible Übereinstimmung gibt,
setze candidate_person_id auf exakt eine der
bereitgestellten IDs.

Beispiele:
- "meine erste Freundin" könnte zu einer bereits
  bekannten Person passen, deren Relationship
  "erste Freundin" ist.
- "Trini" könnte zu einer bekannten Trini passen.
- "meine Mutter" könnte zu einer bekannten Mutter
  passen.

Aber:
Gleicher Vorname allein reicht bei häufigen Namen
nicht automatisch als sichere Identität.

Bei plausibler, aber nicht vollständig sicherer
Übereinstimmung:
needs_identity_clarification = true

und stelle eine kurze natürliche Frage wie:

"Ist die erste Freundin, von der du gerade
erzählst, dieselbe Trini, von der du schon einmal
erzählt hast?"

Die Frage soll verständlich sein und Roman
die Verbindung bestätigen oder ablehnen lassen.

Keine heimliche Verschmelzung.

--------------------------------------------------
RELATIONSHIPS
--------------------------------------------------

relationship_to_narrator:
Beziehung dieser Person zu Roman.

Zum Beispiel:
Mutter
Vater
Bruder
Schwester
Freund
erste Freundin
Ehefrau
Kollege
Chef
Nachbar
Lehrer

Keine künstliche Standardisierung erzwingen,
wenn Romans natürliche Formulierung genauer ist.

Eine Person darf im Laufe ihres Lebens mehrere
Beziehungen oder Phasen zu Roman haben.

--------------------------------------------------
PERSON ↔ PERSON
--------------------------------------------------

person_relationships enthält nur Beziehungen
zwischen zwei erwähnten Personen, wenn Roman
sie tatsächlich erwähnt.

Beispiele:
"Peter war der Bruder von Hans."
"Trini kannte meinen Cousin Klaus."

Keine Beziehungen erfinden.

--------------------------------------------------
IDENTITÄTS-AUFLÖSUNG
--------------------------------------------------

Falls die AKTUELLE Antwort auf eine direkte
Identitäts-Klärungsfrage antwortet, darf
identity_resolution verwendet werden.

resolution darf sein:
- "confirmed"
- "rejected"
- "unclear"
- "none"

Nur confirmed oder rejected, wenn Roman es
wirklich klar bestätigt oder verneint.

Kein Raten.

--------------------------------------------------
TIMELINE
--------------------------------------------------

timeline_year:
Nur eine vierstellige Jahreszahl, wenn sich aus
Romans Erzählung selbst ein belastbares Jahr
ergibt.

timeline_label:
Natürliche Formulierung wie:
"1945"
"etwa 1950"
"Sommer 1962"

timeline_confidence:
"exact" bei klar genanntem Jahr.
"approximate" bei von Roman selbst ungefähr
genanntem Jahr.
"unknown" sonst.

KEIN historisches Weltwissen zur Datierung.
Keine Jahreszahl erraten.

--------------------------------------------------
PRIVACY
--------------------------------------------------

privacy_signal = true NUR wenn Roman ausdrücklich
signalisiert, dass etwas vertraulich bleiben soll.

TRUE zum Beispiel:
"Das bleibt unter uns."
"Das sage ich dir im Vertrauen."
"Das soll nicht jeder wissen."
"Das soll nur die Familie wissen."

FALSE zum Beispiel:
"Das ist kein Geheimnis."
"Das kann ruhig jeder wissen."
Persönlicher Inhalt allein ist KEIN Privacy-Signal.

--------------------------------------------------
GRUNDREGEL
--------------------------------------------------

Roman bestätigte Informationen sind wichtiger
als KI-Vermutungen.

Niemals eine Person, Beziehung, Emotion oder
Tatsache erfinden.
"""

    response = (
        openai_client
        .responses
        .create(
            model="gpt-5-mini",
            input=prompt,
        )
    )

    return parse_json_response(
        response.output_text
        or ""
    )


# =========================================================
# KI: EMPATHISCHE, TIEFE FOLGEFRAGE
# =========================================================

def generate_follow_up_question(
    answer: dict,
    analysis: dict,
    pending_identity_candidates: list,
):
    full_context = build_full_memory_context(
        answer
    )

    # Identitätsklärung hat Vorrang, wenn sie
    # notwendig ist, damit wir keine Menschen
    # falsch miteinander verbinden.
    if pending_identity_candidates:
        first = pending_identity_candidates[0]

        clarification = clean_text(
            first.get(
                "clarification_question"
            )
        )

        if clarification:
            return clarification

    summary = clean_text(
        analysis.get("summary")
    )

    topics = analysis.get(
        "topics",
        [],
    ) or []

    people = analysis.get(
        "people",
        [],
    ) or []

    places = analysis.get(
        "places",
        [],
    ) or []

    unresolved_people = []

    for person in people:
        if not isinstance(
            person,
            dict,
        ):
            continue

        relationship = clean_text(
            person.get(
                "relationship_to_narrator"
            )
        )

        mentioned_as = clean_text(
            person.get(
                "mentioned_as"
            )
        )

        if (
            mentioned_as
            and not relationship
        ):
            unresolved_people.append(
                mentioned_as
            )

    prompt = f"""
Du führst mit Roman ein warmes, respektvolles
Gespräch über sein Leben.

Deine einzige Aufgabe:
Formuliere eine kurze menschliche Reaktion und,
wenn wirklich sinnvoll, EINE hervorragende
Folgefrage.

Du sollst NICHT möglichst viele Daten sammeln.
Du sollst NICHT psychologisieren.
Du sollst NICHT Roman analysieren.

Das Ziel ist:
eine Tür zu öffnen, durch die Roman freiwillig
noch etwas Bedeutungsvolles erzählen möchte.

GESAMTER BISHERIGER ERINNERUNGSKONTEXT:

{full_context}

KURZE ARCHIV-ZUSAMMENFASSUNG:
{summary}

THEMEN:
{json.dumps(topics, ensure_ascii=False)}

PERSONEN:
{json.dumps(people, ensure_ascii=False)}

ORTE:
{json.dumps(places, ensure_ascii=False)}

PERSONEN MIT NOCH UNKLARER BEZIEHUNG ZU ROMAN:
{json.dumps(unresolved_people, ensure_ascii=False)}

--------------------------------------------------
DAS WICHTIGSTE: TIEFE VOR OBERFLÄCHE
--------------------------------------------------

Wenn Roman einen Gegenstand, ein Geräusch,
ein Zimmer, Vorhänge, ein Auto oder Ähnliches
erwähnt, frage NICHT automatisch nach einem
weiteren äußerlichen Detail.

Schlecht:
Roman erwähnt Vorhänge.
Frage: "Wie sahen die Vorhänge aus?"

Besser:
"Was verbindest du heute mit der Zeit,
in der du dort gelebt hast?"

Schlecht:
Roman erinnert sich an das Lachen seiner Mutter.
Frage: "Wie klang ihr Lachen?"

Besser:
"Was bedeutete deine Mutter damals für dich?"

Schlecht:
Roman erwähnt einen roten Opel.
Frage: "Welches Modell war das?"

Besser, wenn es inhaltlich passt:
"Was bedeutete dieses Auto damals für dich –
war es eher Freiheit, Familie, ein Neuanfang
oder etwas ganz anderes?"

--------------------------------------------------
PRIORITÄT FÜR GUTE FRAGEN
--------------------------------------------------

Bevorzuge, sofern im Kontext begründet:

1. Bedeutung
2. wichtige Beziehungen
3. inneres Erleben
4. Wendepunkte und Entscheidungen
5. Identität und Selbstbild
6. was Roman später anders verstanden hat
7. heutige Sicht auf die damalige Zeit
8. etwas damals Ungesagtes
9. Verlust, Stolz, Liebe, Hoffnung oder Bedauern,
   aber NUR wenn der Kontext dafür eine echte
   Grundlage liefert
10. konkrete Szenen- oder Sinnesdetails erst
    deutlich später

--------------------------------------------------
PERSONEN
--------------------------------------------------

Wenn eine neu erwähnte Person offensichtlich
wichtig ist und ihre Beziehung zu Roman noch
unklar ist, darf die Folgefrage genau dort
ansetzen.

Zum Beispiel:
"Du hast gerade Trini erwähnt. Wer war sie
damals für dich?"

Aber nur dann, wenn das natürlicher und
biografisch wertvoller ist als eine andere
Tiefenfrage.

Wenn die Beziehung bereits bekannt ist,
frage nicht noch einmal:
"Wer war sie für dich?"

Dann gehe tiefer.

Zum Beispiel:
"Du hast Trini als deine erste Freundin
beschrieben. Was mochtest du damals besonders
an ihr?"

--------------------------------------------------
KEINE WIEDERHOLUNG
--------------------------------------------------

Lies den GESAMTEN Erinnerungskontext.

Frage NICHT nach etwas, das Roman bereits
beantwortet hat.

Paraphrasiere auch nicht einfach dieselbe Frage.

--------------------------------------------------
EMPATHISCHE REAKTION
--------------------------------------------------

Du darfst vor der Frage einen kurzen,
menschlichen Satz sagen.

Zum Beispiel:
"Das klingt nach einer wirklich schweren Zeit."
"Da scheint dir ein besonderer Moment geblieben
zu sein."
"Das klingt nach einer Zeit, die viel für dich
bedeutet hat."

Aber:
Behaupte Gefühle niemals als Tatsache, wenn Roman
sie nicht selbst genannt hat.

Nicht:
"Du warst bestimmt völlig verzweifelt."

Besser:
"Das klingt, als könnte das eine schwere Zeit
gewesen sein."

Maximal zwei kurze Sätze insgesamt vor der Frage.

--------------------------------------------------
FREIWILLIGKEIT
--------------------------------------------------

Persönliche Fragen sind erlaubt, aber Roman darf
jederzeit nicht antworten.

Gelegentlich, nicht mechanisch:
"Wenn du darüber erzählen möchtest ..."
"Falls du dich daran erinnern magst ..."

Keine Manipulation.
Kein Druck.
Keine Therapie-Sprache.
Keine Diagnosen.
Keine Behauptungen über unbewusste Motive.

--------------------------------------------------
EMOJIS
--------------------------------------------------

Normalerweise KEIN Emoji.

Wenn wirklich passend:
maximal EIN Emoji und ausschließlich:
🙂 😔 ❤️ 😮

Bei Tod, Krieg, Trauma, Gewalt, schwerer Krankheit
oder sehr intimen Geschichten möglichst kein
Emoji.

--------------------------------------------------
QUALITÄT VOR QUANTITÄT
--------------------------------------------------

Überlege intern mehrere mögliche Folgefragen
und wähle nur die beste.

Gib deine Überlegungen NICHT aus.

Wenn keine wirklich gute neue Frage existiert,
gib einen leeren String zurück.

Antworte ausschließlich mit gültigem JSON:

{{
  "follow_up_question": ""
}}
"""

    try:
        response = (
            openai_client
            .responses
            .create(
                model="gpt-5-mini",
                input=prompt,
            )
        )

        result = parse_json_response(
            response.output_text
            or ""
        )

        follow_up = clean_text(
            result.get(
                "follow_up_question"
            )
        )

        if (
            follow_up
            and len(follow_up) < 15
        ):
            return ""

        return follow_up

    except Exception as exc:
        print(
            "FOLLOW-UP GENERATION ERROR:",
            exc,
        )

        # Analyse darf nicht fehlschlagen,
        # nur weil die Folgefrage scheitert.
        return ""


# =========================================================
# PERSONENANALYSE VERARBEITEN
# =========================================================

def process_people_analysis(
    answer: dict,
    analysis: dict,
):
    profile_id = answer["profile_id"]
    answer_id = answer["id"]

    known_people_before = (
        get_known_people(
            profile_id
        )
    )

    people_data = analysis.get(
        "people",
        [],
    ) or []

    created_people = []
    pending_candidates = []
    mention_person_map = {}

    for raw_person in people_data:
        if not isinstance(
            raw_person,
            dict,
        ):
            continue

        mentioned_as = clean_text(
            raw_person.get(
                "mentioned_as"
            )
        )

        name = clean_text(
            raw_person.get("name")
        )

        if (
            not mentioned_as
            and not name
        ):
            continue

        source_person = (
            create_provisional_person(
                profile_id,
                raw_person,
            )
        )

        created_people.append(
            source_person
        )

        source_person_id = (
            source_person["id"]
        )

        mention_key = normalize_name(
            mentioned_as or name
        )

        if mention_key:
            mention_person_map[
                mention_key
            ] = source_person_id

        # Alias aus mentioned_as nur speichern,
        # wenn er sich sinnvoll vom Hauptnamen
        # unterscheidet.
        if (
            mentioned_as
            and normalize_name(
                mentioned_as
            )
            != normalize_name(name)
        ):
            add_alias_if_missing(
                source_person_id,
                mentioned_as,
            )

        for alias in (
            raw_person.get(
                "aliases",
                []
            )
            or []
        ):
            add_alias_if_missing(
                source_person_id,
                clean_text(alias),
            )

        relationship = clean_text(
            raw_person.get(
                "relationship_to_narrator"
            )
        )

        if relationship:
            add_narrator_relationship(
                profile_id=
                    profile_id,
                person_id=
                    source_person_id,
                answer_id=
                    answer_id,
                relationship_type=
                    relationship,
                description=
                    raw_person.get(
                        "description"
                    ),
                start_year=
                    raw_person.get(
                        "relationship_start_year"
                    ),
                end_year=
                    raw_person.get(
                        "relationship_end_year"
                    ),
                confidence=
                    raw_person.get(
                        "confidence",
                        "medium",
                    ),
                status=
                    "inferred",
            )

        for fact in (
            raw_person.get(
                "facts",
                []
            )
            or []
        ):
            if not isinstance(
                fact,
                dict,
            ):
                continue

            add_person_fact(
                profile_id=
                    profile_id,
                person_id=
                    source_person_id,
                answer_id=
                    answer_id,
                fact_type=
                    fact.get("type"),
                fact_value=
                    fact.get("value"),
                confidence=
                    fact.get(
                        "confidence",
                        "medium",
                    ),
                status=
                    "inferred",
            )

        candidate_person_id = clean_text(
            raw_person.get(
                "candidate_person_id"
            )
        )

        valid_known_ids = {
            str(person["id"])
            for person
            in known_people_before
        }

        if (
            candidate_person_id
            not in valid_known_ids
        ):
            candidate_person_id = ""

        if not candidate_person_id:
            name_candidate = (
                find_name_candidate(
                    known_people_before,
                    name or mentioned_as,
                )
            )

            if name_candidate:
                candidate_person_id = str(
                    name_candidate["id"]
                )

        if (
            candidate_person_id
            and candidate_person_id
            != str(source_person_id)
        ):
            clarification = clean_text(
                raw_person.get(
                    "clarification_question"
                )
            )

            if not clarification:
                candidate_person = next(
                    (
                        person
                        for person
                        in known_people_before
                        if str(
                            person["id"]
                        )
                        == candidate_person_id
                    ),
                    None,
                )

                candidate_name = (
                    clean_text(
                        candidate_person.get(
                            "name"
                        )
                    )
                    if candidate_person
                    else ""
                )

                current_label = (
                    mentioned_as
                    or name
                    or "diese Person"
                )

                if candidate_name:
                    clarification = (
                        f"Ist {current_label} "
                        f"dieselbe Person wie "
                        f"{candidate_name}, von "
                        f"der du schon einmal "
                        f"erzählt hast?"
                    )
                else:
                    clarification = (
                        "Ist diese Person "
                        "dieselbe, von der du "
                        "schon einmal erzählt "
                        "hast?"
                    )

            candidate = (
                create_identity_candidate(
                    profile_id=
                        profile_id,
                    answer_id=
                        answer_id,
                    source_person_id=
                        source_person_id,
                    candidate_person_id=
                        candidate_person_id,
                    mentioned_name=
                        mentioned_as or name,
                    confidence_score=
                        raw_person.get(
                            "identity_confidence",
                            0.5,
                        ),
                    reason=
                        raw_person.get(
                            "identity_reason",
                            "",
                        ),
                    clarification_question=
                        clarification,
                )
            )

            if candidate:
                pending_candidates.append(
                    candidate
                )

            identification_status = (
                "probable"
            )
        else:
            identification_status = (
                "unconfirmed"
            )

        link_person_to_answer(
            answer_id=
                answer_id,
            person_id=
                source_person_id,
            mentioned_as=
                mentioned_as or name,
            context=
                raw_person.get(
                    "description",
                    "",
                ),
            confidence=
                raw_person.get(
                    "confidence",
                    "medium",
                ),
            role_in_memory=
                raw_person.get(
                    "role_in_memory",
                    "",
                ),
            identification_status=
                identification_status,
        )

    # -----------------------------------------------------
    # PERSON ↔ PERSON RELATIONSHIPS
    # -----------------------------------------------------

    person_relationships = (
        analysis.get(
            "person_relationships",
            [],
        )
        or []
    )

    for relation in person_relationships:
        if not isinstance(
            relation,
            dict,
        ):
            continue

        a_key = normalize_name(
            relation.get(
                "person_a_mentioned_as"
            )
        )

        b_key = normalize_name(
            relation.get(
                "person_b_mentioned_as"
            )
        )

        person_a_id = (
            mention_person_map.get(a_key)
        )

        person_b_id = (
            mention_person_map.get(b_key)
        )

        relationship_type = clean_text(
            relation.get(
                "relationship_type"
            )
        )

        if (
            not person_a_id
            or not person_b_id
            or person_a_id
            == person_b_id
            or not relationship_type
        ):
            continue

        (
            supabase
            .table(
                "person_relationships"
            )
            .insert(
                {
                    "profile_id":
                        profile_id,
                    "person_a_id":
                        person_a_id,
                    "person_b_id":
                        person_b_id,
                    "relationship_type":
                        relationship_type,
                    "description":
                        clean_text(
                            relation.get(
                                "description"
                            )
                        )
                        or None,
                    "confidence":
                        normalize_confidence(
                            relation.get(
                                "confidence",
                                "medium",
                            )
                        ),
                    "source_answer_id":
                        answer_id,
                    "status":
                        "inferred",
                }
            )
            .execute()
        )

    return {
        "created_people":
            created_people,
        "pending_candidates":
            pending_candidates,
    }


# =========================================================
# IDENTITÄTSANTWORT AUTOMATISCH ZUORDNEN
# =========================================================

def maybe_resolve_identity_from_followup(
    answer: dict,
    analysis: dict,
    current_user,
):
    question = get_question_or_none(
        answer.get("question_id")
    )

    if not question:
        return None

    parent_answer_id = question.get(
        "parent_answer_id"
    )

    if not parent_answer_id:
        return None

    pending_result = (
        supabase
        .table(
            "person_identity_candidates"
        )
        .select("*")
        .eq(
            "answer_id",
            parent_answer_id,
        )
        .eq(
            "status",
            "pending",
        )
        .order(
            "created_at",
        )
        .execute()
    )

    pending = (
        pending_result.data
        or []
    )

    if not pending:
        return None

    question_text = clean_text(
        question.get("text")
    )

    candidate = None

    for row in pending:
        clarification = clean_text(
            row.get(
                "clarification_question"
            )
        )

        if (
            clarification
            and question_text
            and normalize_name(
                clarification
            )
            == normalize_name(
                question_text
            )
        ):
            candidate = row
            break

    if not candidate:
        if len(pending) == 1:
            candidate = pending[0]
        else:
            return None

    identity_resolution = (
        analysis.get(
            "identity_resolution",
            {}
        )
        or {}
    )

    resolution = clean_text(
        identity_resolution.get(
            "resolution"
        )
    ).lower()

    if resolution == "confirmed":
        return (
            resolve_identity_candidate_internal(
                candidate,
                same_person=True,
                resolved_by=
                    current_user.get("id"),
            )
        )

    if resolution == "rejected":
        return (
            resolve_identity_candidate_internal(
                candidate,
                same_person=False,
                resolved_by=
                    current_user.get("id"),
            )
        )

    return None


# =========================================================
# AUDIO-HILFSFUNKTION
# =========================================================

def convert_audio_to_wav(
    audio_bytes: bytes,
    extension: str,
):
    source_file = None
    wav_file = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{extension}",
        ) as temp_source:
            temp_source.write(
                audio_bytes
            )
            source_file = temp_source.name

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        ) as temp_wav:
            wav_file = temp_wav.name

        command = [
            FFMPEG_PATH,
            "-y",
            "-i",
            source_file,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            wav_file,
        ]

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if process.returncode != 0:
            print(
                "FFMPEG ERROR:",
                process.stderr,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Audio konnte nicht "
                    "vorbereitet werden."
                ),
            )

        with open(
            wav_file,
            "rb",
        ) as handle:
            wav_bytes = handle.read()

        return wav_bytes

    finally:
        for path in (
            source_file,
            wav_file,
        ):
            if (
                path
                and os.path.exists(path)
            ):
                try:
                    os.remove(path)
                except OSError:
                    pass


def transcribe_audio_bytes(
    audio_bytes: bytes,
    extension: str,
):
    wav_bytes = convert_audio_to_wav(
        audio_bytes,
        extension,
    )

    wav_file = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        ) as temp_wav:
            temp_wav.write(
                wav_bytes
            )
            wav_file = temp_wav.name

        with open(
            wav_file,
            "rb",
        ) as audio_handle:
            transcription = (
                openai_client
                .audio
                .transcriptions
                .create(
                    model=
                        "gpt-4o-mini-transcribe",
                    file=
                        audio_handle,
                    language=
                        "de",
                )
            )

        return clean_text(
            transcription.text
        )

    finally:
        if (
            wav_file
            and os.path.exists(
                wav_file
            )
        ):
            try:
                os.remove(wav_file)
            except OSError:
                pass


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# =========================================================
# AKTUELLER BENUTZER
# =========================================================

@app.get("/me")
def me(
    current_user=Depends(
        get_current_app_user
    )
):
    return {
        "id":
            current_user["id"],
        "auth_user_id":
            current_user["auth_user_id"],
        "display_name":
            current_user["display_name"],
        "role":
            current_user["role"],
        "profile_id":
            current_user.get(
                "profile_id"
            ),
        "email":
            current_user.get(
                "email"
            ),
    }


# =========================================================
# PROFILE
# =========================================================

@app.get("/profiles")
def profiles(
    current_user=Depends(
        get_current_app_user
    )
):
    role = current_user["role"]

    if role in (
        "admin",
        "reader",
    ):
        result = (
            supabase
            .table("profiles")
            .select("*")
            .order("display_name")
            .execute()
        )

        return result.data

    if role == "narrator":
        profile_id = current_user.get(
            "profile_id"
        )

        if not profile_id:
            return []

        result = (
            supabase
            .table("profiles")
            .select("*")
            .eq(
                "id",
                profile_id,
            )
            .execute()
        )

        return result.data

    raise HTTPException(
        status_code=403,
        detail="Keine Berechtigung.",
    )


# =========================================================
# ARCHIV
# =========================================================

@app.get("/archive")
def archive(
    profile_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    authorize_read_profile(
        current_user,
        profile_id,
    )

    answers_result = (
        supabase
        .table("answers")
        .select(
            "id, profile_id, question_id, "
            "original_transcript, edited_transcript, "
            "transcript_version, needs_reanalysis, "
            "visibility, audio_path, answered_at, "
            "created_at, timeline_year, timeline_label, "
            "timeline_confidence"
        )
        .eq(
            "profile_id",
            profile_id,
        )
        .order(
            "answered_at",
            desc=True,
        )
        .execute()
    )

    answers = (
        answers_result.data
        or []
    )

    if not answers:
        return {
            "items": []
        }

    answer_ids = [
        row["id"]
        for row in answers
    ]

    memories_result = (
        supabase
        .table("memories")
        .select("*")
        .in_(
            "answer_id",
            answer_ids,
        )
        .execute()
    )

    memory_map = {
        row["answer_id"]: row
        for row in (
            memories_result.data
            or []
        )
    }

    supplements_result = (
        supabase
        .table("answer_supplements")
        .select("*")
        .in_(
            "answer_id",
            answer_ids,
        )
        .order("created_at")
        .execute()
    )

    supplements_map = {}

    for supplement in (
        supplements_result.data
        or []
    ):
        supplements_map.setdefault(
            supplement["answer_id"],
            [],
        ).append(
            supplement
        )

    answer_people_result = (
        supabase
        .table("answer_people")
        .select("*")
        .in_(
            "answer_id",
            answer_ids,
        )
        .execute()
    )

    answer_people_map = {}

    person_ids = set()

    for link in (
        answer_people_result.data
        or []
    ):
        answer_people_map.setdefault(
            link["answer_id"],
            [],
        ).append(link)

        if link.get("person_id"):
            person_ids.add(
                link["person_id"]
            )

    people_map = {}

    if person_ids:
        people_result = (
            supabase
            .table("people")
            .select("*")
            .in_(
                "id",
                list(person_ids),
            )
            .execute()
        )

        people_map = {
            row["id"]: row
            for row in (
                people_result.data
                or []
            )
        }

    question_ids = list(
        {
            row["question_id"]
            for row in answers
            if row.get(
                "question_id"
            )
        }
    )

    question_map = {}

    if question_ids:
        question_result = (
            supabase
            .table("questions")
            .select(
                "id, text, category, "
                "source, parent_answer_id"
            )
            .in_(
                "id",
                question_ids,
            )
            .execute()
        )

        question_map = {
            row["id"]: row
            for row in (
                question_result.data
                or []
            )
        }

    items = []

    for answer in answers:
        question = None

        if answer.get(
            "question_id"
        ):
            question = question_map.get(
                answer["question_id"]
            )

        links = answer_people_map.get(
            answer["id"],
            [],
        )

        people = []

        for link in links:
            person = people_map.get(
                link.get(
                    "person_id"
                )
            )

            if not person:
                continue

            people.append(
                {
                    "person":
                        person,
                    "mention":
                        link,
                }
            )

        current_transcript = (
            clean_text(
                answer.get(
                    "edited_transcript"
                )
            )
            or clean_text(
                answer.get(
                    "original_transcript"
                )
            )
        )

        items.append(
            {
                "answer_id":
                    answer["id"],
                "question":
                    question,
                "is_free_memory":
                    answer.get(
                        "question_id"
                    ) is None,
                "transcript":
                    current_transcript,
                "original_transcript":
                    answer.get(
                        "original_transcript"
                    )
                    or "",
                "edited_transcript":
                    answer.get(
                        "edited_transcript"
                    ),
                "transcript_version":
                    answer.get(
                        "transcript_version"
                    )
                    or 1,
                "needs_reanalysis":
                    bool(
                        answer.get(
                            "needs_reanalysis"
                        )
                    ),
                "supplements":
                    supplements_map.get(
                        answer["id"],
                        [],
                    ),
                "people":
                    people,
                "visibility":
                    answer.get(
                        "visibility"
                    )
                    or "all",
                "has_audio":
                    bool(
                        answer.get(
                            "audio_path"
                        )
                    ),
                "answered_at":
                    answer.get(
                        "answered_at"
                    ),
                "created_at":
                    answer.get(
                        "created_at"
                    ),
                "timeline_year":
                    answer.get(
                        "timeline_year"
                    ),
                "timeline_label":
                    answer.get(
                        "timeline_label"
                    ),
                "timeline_confidence":
                    answer.get(
                        "timeline_confidence"
                    ),
                "memory":
                    memory_map.get(
                        answer["id"]
                    ),
            }
        )

    return {
        "items": items
    }


# =========================================================
# PERSONEN-ARCHIV
# =========================================================

@app.get("/people")
def people(
    profile_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    authorize_read_profile(
        current_user,
        profile_id,
    )

    return {
        "items":
            get_known_people(
                profile_id
            )
    }


@app.get("/people/{person_id}")
def person_detail(
    person_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    person = get_person_or_404(
        person_id
    )

    authorize_read_profile(
        current_user,
        person["profile_id"],
    )

    aliases = (
        supabase
        .table("person_aliases")
        .select("*")
        .eq(
            "person_id",
            person_id,
        )
        .execute()
    )

    narrator_relationships = (
        supabase
        .table(
            "person_narrator_relationships"
        )
        .select("*")
        .eq(
            "person_id",
            person_id,
        )
        .order("created_at")
        .execute()
    )

    facts = (
        supabase
        .table("person_facts")
        .select("*")
        .eq(
            "person_id",
            person_id,
        )
        .order("created_at")
        .execute()
    )

    mentions = (
        supabase
        .table("answer_people")
        .select("*")
        .eq(
            "person_id",
            person_id,
        )
        .order("created_at")
        .execute()
    )

    relations_a = (
        supabase
        .table("person_relationships")
        .select("*")
        .eq(
            "person_a_id",
            person_id,
        )
        .neq(
            "status",
            "rejected",
        )
        .execute()
    )

    relations_b = (
        supabase
        .table("person_relationships")
        .select("*")
        .eq(
            "person_b_id",
            person_id,
        )
        .neq(
            "status",
            "rejected",
        )
        .execute()
    )

    return {
        "person":
            person,
        "aliases":
            aliases.data or [],
        "relationships_to_roman":
            narrator_relationships.data
            or [],
        "facts":
            facts.data or [],
        "mentions":
            mentions.data or [],
        "person_relationships":
            (
                relations_a.data
                or []
            )
            + (
                relations_b.data
                or []
            ),
    }


# =========================================================
# ZEITANGABE ÄNDERN
# =========================================================

@app.post(
    "/answer/{answer_id}/timeline"
)
def update_timeline(
    answer_id: str,
    payload: TimelineUpdate,
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    if (
        payload.timeline_confidence
        not in (
            None,
            "exact",
            "approximate",
            "unknown",
        )
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Ungültige "
                "timeline_confidence."
            ),
        )

    if (
        payload.timeline_year
        is not None
        and (
            payload.timeline_year < 1800
            or payload.timeline_year > 2100
        )
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Bitte eine plausible "
                "Jahreszahl eingeben."
            ),
        )

    label = (
        clean_text(
            payload.timeline_label
        )
        or None
    )

    confidence = (
        payload.timeline_confidence
        or (
            "unknown"
            if payload.timeline_year
            is None
            else "approximate"
        )
    )

    family_result = (
        update_timeline_family(
            answer=answer,
            timeline_year=
                payload.timeline_year,
            timeline_label=
                label,
            timeline_confidence=
                confidence,
        )
    )

    updated_answer = (
        get_answer_or_404(
            answer_id
        )
    )

    return {
        "status":
            "updated",
        "answer":
            updated_answer,
        "root_answer_id":
            family_result[
                "root_answer_id"
            ],
        "updated_answer_ids":
            family_result[
                "answer_ids"
            ],
    }


# =========================================================
# TRANSKRIPT KORRIGIEREN
# =========================================================

@app.post(
    "/answer/{answer_id}/transcript"
)
def update_transcript(
    answer_id: str,
    payload: TranscriptUpdate,
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    new_text = clean_text(
        payload.text
    )

    if not new_text:
        raise HTTPException(
            status_code=400,
            detail=(
                "Der korrigierte Text "
                "darf nicht leer sein."
            ),
        )

    original = clean_text(
        answer.get(
            "original_transcript"
        )
    )

    if not original:
        raise HTTPException(
            status_code=400,
            detail=(
                "Es gibt noch kein "
                "Originaltranskript."
            ),
        )

    ensure_original_revision(
        answer_id,
        original,
    )

    current_version = (
        safe_int(
            answer.get(
                "transcript_version"
            )
        )
        or 1
    )

    new_version = (
        current_version + 1
    )

    (
        supabase
        .table(
            "answer_transcript_revisions"
        )
        .insert(
            {
                "answer_id":
                    answer_id,
                "version_number":
                    new_version,
                "transcript":
                    new_text,
                "change_type":
                    "correction",
                "change_note":
                    clean_text(
                        payload.change_note
                    )
                    or None,
                "changed_by":
                    current_user.get(
                        "id"
                    ),
            }
        )
        .execute()
    )

    result = (
        supabase
        .table("answers")
        .update(
            {
                "edited_transcript":
                    new_text,
                "transcript_version":
                    new_version,
                "needs_reanalysis":
                    True,
            }
        )
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    return {
        "status":
            "updated",
        "answer":
            (
                result.data[0]
                if result.data
                else get_answer_or_404(
                    answer_id
                )
            ),
        "needs_reanalysis":
            True,
    }


@app.get(
    "/answer/{answer_id}/revisions"
)
def transcript_revisions(
    answer_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_read_profile(
        current_user,
        answer["profile_id"],
    )

    result = (
        supabase
        .table(
            "answer_transcript_revisions"
        )
        .select("*")
        .eq(
            "answer_id",
            answer_id,
        )
        .order(
            "version_number",
        )
        .execute()
    )

    return {
        "items":
            result.data or []
    }


# =========================================================
# ERGÄNZUNGEN / PRÄZISIERUNGEN
# =========================================================

@app.post(
    "/answer/{answer_id}/supplement"
)
def create_supplement(
    answer_id: str,
    payload: SupplementCreate,
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    if payload.supplement_type not in (
        "clarification",
        "addition",
        "correction_note",
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Ungültiger "
                "supplement_type."
            ),
        )

    transcript = clean_text(
        payload.transcript
    )

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail=(
                "Die Ergänzung darf "
                "nicht leer sein."
            ),
        )

    result = (
        supabase
        .table("answer_supplements")
        .insert(
            {
                "answer_id":
                    answer_id,
                "transcript":
                    transcript,
                "supplement_type":
                    payload.supplement_type,
                "created_by":
                    current_user.get(
                        "id"
                    ),
            }
        )
        .execute()
    )

    (
        supabase
        .table("answers")
        .update(
            {
                "needs_reanalysis":
                    True,
            }
        )
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    return {
        "status":
            "created",
        "supplement":
            (
                result.data[0]
                if result.data
                else None
            ),
        "needs_reanalysis":
            True,
    }


@app.post(
    "/answer/{answer_id}/supplement/audio"
)
async def create_audio_supplement(
    answer_id: str,
    supplement_type: str = Form(
        "clarification"
    ),
    audio: UploadFile = File(...),
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    if supplement_type not in (
        "clarification",
        "addition",
        "correction_note",
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Ungültiger "
                "supplement_type."
            ),
        )

    filename = (
        audio.filename
        or "ergaenzung.webm"
    )

    extension = (
        filename.rsplit(
            ".",
            1,
        )[-1].lower()
        if "." in filename
        else "webm"
    )

    if extension not in {
        "webm",
        "wav",
        "mp3",
        "m4a",
        "ogg",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "Nicht unterstütztes "
                "Audioformat."
            ),
        )

    file_bytes = await audio.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Audiodatei ist leer.",
        )

    now = datetime.now(
        timezone.utc
    )

    storage_path = (
        f"{answer['profile_id']}/"
        f"{now.year}/"
        f"{now.month:02d}/"
        f"supplement-"
        f"{uuid4()}.{extension}"
    )

    try:
        (
            supabase
            .storage
            .from_("memories-audio")
            .upload(
                storage_path,
                file_bytes,
                {
                    "content-type":
                        audio.content_type
                        or
                        "application/octet-stream",
                    "upsert":
                        "false",
                },
            )
        )

    except Exception as exc:
        print(
            "SUPPLEMENT UPLOAD ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Ergänzungs-Audio konnte "
                "nicht gespeichert werden."
            ),
        )

    transcript = (
        transcribe_audio_bytes(
            file_bytes,
            extension,
        )
    )

    result = (
        supabase
        .table("answer_supplements")
        .insert(
            {
                "answer_id":
                    answer_id,
                "transcript":
                    transcript,
                "audio_path":
                    storage_path,
                "supplement_type":
                    supplement_type,
                "created_by":
                    current_user.get(
                        "id"
                    ),
            }
        )
        .execute()
    )

    (
        supabase
        .table("answers")
        .update(
            {
                "needs_reanalysis":
                    True,
            }
        )
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    return {
        "status":
            "created",
        "transcript":
            transcript,
        "supplement":
            (
                result.data[0]
                if result.data
                else None
            ),
        "needs_reanalysis":
            True,
    }


# =========================================================
# NÄCHSTE FRAGE
# =========================================================

@app.get("/question/next")
def next_question(
    profile_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    authorize_profile(
        current_user,
        profile_id,
    )

    profile_result = (
        supabase
        .table("profiles")
        .select("id")
        .eq(
            "id",
            profile_id,
        )
        .limit(1)
        .execute()
    )

    if not profile_result.data:
        raise HTTPException(
            status_code=404,
            detail="Profil nicht gefunden.",
        )

    questions_result = (
        supabase
        .table("questions")
        .select("*")
        .neq(
            "source",
            "follow_up",
        )
        .execute()
    )

    questions = (
        questions_result.data
        or []
    )

    if not questions:
        raise HTTPException(
            status_code=404,
            detail="Keine Fragen vorhanden.",
        )

    history_result = (
        supabase
        .table("question_history")
        .select(
            "question_id, status"
        )
        .eq(
            "profile_id",
            profile_id,
        )
        .execute()
    )

    answered_ids = {
        row["question_id"]
        for row in (
            history_result.data
            or []
        )
        if (
            row.get("status")
            == "answered"
            and row.get(
                "question_id"
            )
        )
    }

    available = [
        question
        for question in questions
        if question["id"]
        not in answered_ids
    ]

    if not available:
        available = questions

    selected = random.choice(
        available
    )

    history_insert = (
        supabase
        .table("question_history")
        .insert(
            {
                "profile_id":
                    profile_id,
                "question_id":
                    selected["id"],
                "status":
                    "shown",
                "shown_at":
                    utc_now_iso(),
            }
        )
        .execute()
    )

    history = (
        history_insert.data[0]
    )

    return {
        "history_id":
            history["id"],
        "question":
            selected,
    }


# =========================================================
# FOLGEFRAGE
# =========================================================

@app.post("/question/follow-up")
def create_follow_up(
    payload: FollowUpCreate,
    current_user=Depends(
        get_current_app_user
    ),
):
    authorize_profile(
        current_user,
        payload.profile_id,
    )

    text = clean_text(
        payload.text
    )

    if not text:
        raise HTTPException(
            status_code=400,
            detail=(
                "Die Folgefrage "
                "darf nicht leer sein."
            ),
        )

    parent_answer = (
        get_answer_or_404(
            payload.parent_answer_id
        )
    )

    if (
        str(
            parent_answer[
                "profile_id"
            ]
        )
        != str(
            payload.profile_id
        )
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Antwort gehört nicht "
                "zu diesem Profil."
            ),
        )

    question_insert = (
        supabase
        .table("questions")
        .insert(
            {
                "text":
                    text,
                "category":
                    "Nachfrage",
                "source":
                    "follow_up",
                "parent_answer_id":
                    payload.parent_answer_id,
            }
        )
        .execute()
    )

    question = (
        question_insert.data[0]
    )

    history_insert = (
        supabase
        .table("question_history")
        .insert(
            {
                "profile_id":
                    payload.profile_id,
                "question_id":
                    question["id"],
                "status":
                    "shown",
                "shown_at":
                    utc_now_iso(),
            }
        )
        .execute()
    )

    history = (
        history_insert.data[0]
    )

    return {
        "history_id":
            history["id"],
        "question":
            question,
    }


# =========================================================
# FRAGE BEANTWORTET / ÜBERSPRUNGEN
# =========================================================

@app.post(
    "/question/{history_id}/answered"
)
def question_answered(
    history_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    history = get_history_or_404(
        history_id
    )

    authorize_profile(
        current_user,
        history["profile_id"],
    )

    (
        supabase
        .table("question_history")
        .update(
            {
                "status":
                    "answered",
                "answered_at":
                    utc_now_iso(),
            }
        )
        .eq(
            "id",
            history_id,
        )
        .execute()
    )

    return {
        "status": "answered"
    }


@app.post(
    "/question/{history_id}/skipped"
)
def question_skipped(
    history_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    history = get_history_or_404(
        history_id
    )

    authorize_profile(
        current_user,
        history["profile_id"],
    )

    (
        supabase
        .table("question_history")
        .update(
            {
                "status":
                    "skipped",
                "skipped_at":
                    utc_now_iso(),
            }
        )
        .eq(
            "id",
            history_id,
        )
        .execute()
    )

    return {
        "status": "skipped"
    }


# =========================================================
# ANTWORT AUF FRAGE
# =========================================================

@app.post("/answer")
def create_answer(
    answer: AnswerCreate,
    current_user=Depends(
        get_current_app_user
    ),
):
    history = get_history_or_404(
        answer.history_id
    )

    profile_id = history[
        "profile_id"
    ]

    authorize_profile(
        current_user,
        profile_id,
    )

    question_id = history.get(
        "question_id"
    )

    inherited_timeline = (
        get_inherited_timeline_for_question(
            question_id
        )
    )

    text = clean_text(
        answer.text
    )

    insert_data = {
        "profile_id":
            profile_id,
        "session_id":
            history.get(
                "session_id"
            ),
        "question_id":
            question_id,
        "original_transcript":
            text,
        "cleaned_transcript":
            None,
        "visibility":
            "all",
        "include_in_memoir":
            False,
        "answered_at":
            utc_now_iso(),
        "transcript_version":
            1,
        "needs_reanalysis":
            False,
    }

    if inherited_timeline:
        insert_data.update(
            {
                "timeline_year":
                    inherited_timeline.get(
                        "timeline_year"
                    ),
                "timeline_label":
                    inherited_timeline.get(
                        "timeline_label"
                    ),
                "timeline_confidence":
                    inherited_timeline.get(
                        "timeline_confidence"
                    )
                    or "unknown",
            }
        )

    insert_result = (
        supabase
        .table("answers")
        .insert(insert_data)
        .execute()
    )

    created_answer = (
        insert_result.data[0]
    )

    if text:
        ensure_original_revision(
            created_answer["id"],
            text,
        )

    (
        supabase
        .table("question_history")
        .update(
            {
                "status":
                    "answered",
                "answered_at":
                    utc_now_iso(),
            }
        )
        .eq(
            "id",
            answer.history_id,
        )
        .execute()
    )

    return {
        "answer":
            created_answer
    }


# =========================================================
# FREIE ERINNERUNG
# =========================================================

@app.post("/answer/free")
def create_free_answer(
    payload: FreeAnswerCreate,
    current_user=Depends(
        get_current_app_user
    ),
):
    authorize_profile(
        current_user,
        payload.profile_id,
    )

    insert_result = (
        supabase
        .table("answers")
        .insert(
            {
                "profile_id":
                    payload.profile_id,
                "session_id":
                    None,
                "question_id":
                    None,
                "original_transcript":
                    "",
                "cleaned_transcript":
                    None,
                "visibility":
                    "all",
                "include_in_memoir":
                    False,
                "answered_at":
                    utc_now_iso(),
                "timeline_confidence":
                    "unknown",
                "transcript_version":
                    1,
                "needs_reanalysis":
                    False,
            }
        )
        .execute()
    )

    return {
        "answer":
            insert_result.data[0]
    }


# =========================================================
# ENTWURF VERWERFEN
# =========================================================

@app.post(
    "/answer/{answer_id}/discard"
)
def discard_answer(
    answer_id: str,
    payload: DiscardAnswerRequest,
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    history = None

    if payload.history_id:
        history = get_history_or_404(
            payload.history_id
        )

        if (
            str(
                history["profile_id"]
            )
            != str(
                answer["profile_id"]
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Frage und Antwort "
                    "gehören nicht zusammen."
                ),
            )

    audio_paths = []

    if answer.get("audio_path"):
        audio_paths.append(
            answer["audio_path"]
        )

    supplements = get_supplements(
        answer_id
    )

    for supplement in supplements:
        if supplement.get(
            "audio_path"
        ):
            audio_paths.append(
                supplement[
                    "audio_path"
                ]
            )

    if audio_paths:
        try:
            (
                supabase
                .storage
                .from_(
                    "memories-audio"
                )
                .remove(audio_paths)
            )

        except Exception as exc:
            print(
                "AUDIO DELETE WARNING:",
                exc,
            )

    (
        supabase
        .table("answers")
        .delete()
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    if history:
        (
            supabase
            .table(
                "question_history"
            )
            .update(
                {
                    "status":
                        "shown",
                    "answered_at":
                        None,
                    "skipped_at":
                        None,
                }
            )
            .eq(
                "id",
                payload.history_id,
            )
            .execute()
        )

    return {
        "status":
            "discarded",
        "answer_id":
            answer_id,
        "history_id":
            payload.history_id,
    }


# =========================================================
# SICHTBARKEIT
# =========================================================

@app.post(
    "/answer/{answer_id}/visibility"
)
def update_visibility(
    answer_id: str,
    payload: VisibilityUpdate,
    current_user=Depends(
        get_current_app_user
    ),
):
    if payload.visibility not in (
        "family",
        "all",
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "visibility muss "
                "'family' oder 'all' sein."
            ),
        )

    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    result = (
        supabase
        .table("answers")
        .update(
            {
                "visibility":
                    payload.visibility
            }
        )
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    return {
        "status":
            "updated",
        "answer_id":
            answer_id,
        "visibility":
            payload.visibility,
        "answer":
            (
                result.data[0]
                if result.data
                else None
            ),
    }


# =========================================================
# AUDIO UPLOAD
# =========================================================

@app.post("/audio/upload")
async def upload_audio(
    answer_id: str = Form(...),
    audio: UploadFile = File(...),
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    filename = (
        audio.filename
        or "aufnahme.webm"
    )

    extension = (
        filename.rsplit(
            ".",
            1,
        )[-1].lower()
        if "." in filename
        else "webm"
    )

    allowed_extensions = {
        "webm",
        "wav",
        "mp3",
        "m4a",
        "ogg",
    }

    if extension not in (
        allowed_extensions
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Nicht unterstütztes "
                "Audioformat."
            ),
        )

    file_bytes = await audio.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Audiodatei ist leer.",
        )

    now = datetime.now(
        timezone.utc
    )

    storage_path = (
        f"{answer['profile_id']}/"
        f"{now.year}/"
        f"{now.month:02d}/"
        f"{uuid4()}.{extension}"
    )

    try:
        (
            supabase
            .storage
            .from_(
                "memories-audio"
            )
            .upload(
                storage_path,
                file_bytes,
                {
                    "content-type":
                        audio.content_type
                        or
                        "application/octet-stream",
                    "upsert":
                        "false",
                },
            )
        )

    except Exception as exc:
        print(
            "UPLOAD ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Audio konnte nicht "
                "gespeichert werden."
            ),
        )

    (
        supabase
        .table("answers")
        .update(
            {
                "audio_path":
                    storage_path
            }
        )
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    return {
        "status":
            "uploaded",
        "answer_id":
            answer_id,
        "audio_path":
            storage_path,
    }


# =========================================================
# TRANSKRIPTION
# =========================================================

@app.post(
    "/answer/{answer_id}/transcribe"
)
def transcribe_answer(
    answer_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    audio_path = answer.get(
        "audio_path"
    )

    if not audio_path:
        raise HTTPException(
            status_code=400,
            detail=(
                "Für diese Antwort ist "
                "kein Audio gespeichert."
            ),
        )

    try:
        audio_bytes = (
            supabase
            .storage
            .from_(
                "memories-audio"
            )
            .download(
                audio_path
            )
        )

    except Exception as exc:
        print(
            "DOWNLOAD ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Audio konnte nicht "
                "geladen werden."
            ),
        )

    extension = (
        audio_path.rsplit(
            ".",
            1,
        )[-1].lower()
    )

    transcript = (
        transcribe_audio_bytes(
            audio_bytes,
            extension,
        )
    )

    (
        supabase
        .table("answers")
        .update(
            {
                "original_transcript":
                    transcript,
                "edited_transcript":
                    None,
                "transcript_version":
                    1,
                "needs_reanalysis":
                    False,
            }
        )
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    ensure_original_revision(
        answer_id,
        transcript,
    )

    return {
        "status":
            "transcribed",
        "answer_id":
            answer_id,
        "transcript":
            transcript,
    }


# =========================================================
# IDENTITÄTSKANDIDATEN
# =========================================================

@app.get(
    "/person-identity/pending"
)
def pending_identity_candidates(
    profile_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    authorize_read_profile(
        current_user,
        profile_id,
    )

    result = (
        supabase
        .table(
            "person_identity_candidates"
        )
        .select("*")
        .eq(
            "profile_id",
            profile_id,
        )
        .eq(
            "status",
            "pending",
        )
        .order("created_at")
        .execute()
    )

    return {
        "items":
            result.data or []
    }


@app.post(
    "/person-identity/{candidate_id}/resolve"
)
def resolve_identity_candidate(
    candidate_id: str,
    payload: IdentityResolution,
    current_user=Depends(
        get_current_app_user
    ),
):
    candidate = get_candidate_or_404(
        candidate_id
    )

    authorize_profile(
        current_user,
        candidate["profile_id"],
    )

    result = (
        resolve_identity_candidate_internal(
            candidate,
            same_person=
                payload.same_person,
            resolved_by=
                current_user.get("id"),
        )
    )

    return {
        "status":
            "resolved",
        "candidate":
            result,
    }


# =========================================================
# ANALYSE
# =========================================================

@app.post(
    "/answer/{answer_id}/analyze"
)
def analyze_answer(
    answer_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):
    answer = get_answer_or_404(
        answer_id
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    transcript = (
        get_effective_answer_text(
            answer,
            include_supplements=True,
        )
    )

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail=(
                "Die Antwort enthält "
                "noch kein Transkript."
            ),
        )

    # -----------------------------------------------------
    # Bei einer Korrektur / Ergänzung nur KI-Inferenzen
    # entfernen. Menschlich bestätigte Verknüpfungen
    # bleiben bestehen.
    # -----------------------------------------------------

    if answer.get(
        "needs_reanalysis"
    ):
        clear_inferred_data_for_answer(
            answer_id
        )

    # -----------------------------------------------------
    # 1. KI-CALL: ARCHIV + PERSONEN + TIMELINE + PRIVACY
    # -----------------------------------------------------

    try:
        analysis = (
            analyze_memory_with_ai(
                answer
            )
        )

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "ANALYSIS ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "KI-Auswertung "
                "fehlgeschlagen."
            ),
        )

    # -----------------------------------------------------
    # MEMORY SPEICHERN
    # -----------------------------------------------------

    analyzed_people = (
        analysis.get(
            "people",
            [],
        )
        or []
    )

    simple_people = []

    for person in analyzed_people:
        if isinstance(
            person,
            dict,
        ):
            label = (
                clean_text(
                    person.get(
                        "name"
                    )
                )
                or clean_text(
                    person.get(
                        "mentioned_as"
                    )
                )
            )

            if label:
                simple_people.append(
                    label
                )

        elif clean_text(person):
            simple_people.append(
                clean_text(person)
            )

    memory_payload = {
        "answer_id":
            answer_id,
        "summary":
            clean_text(
                analysis.get(
                    "summary"
                )
            ),
        "people":
            simple_people,
        "places":
            analysis.get(
                "places",
                [],
            )
            or [],
        "years":
            analysis.get(
                "years",
                [],
            )
            or [],
        "topics":
            analysis.get(
                "topics",
                [],
            )
            or [],
        "keywords":
            analysis.get(
                "keywords",
                [],
            )
            or [],
    }

    memory_result = (
        supabase
        .table("memories")
        .upsert(
            memory_payload,
            on_conflict="answer_id",
        )
        .execute()
    )

    memory = (
        memory_result.data[0]
        if memory_result.data
        else memory_payload
    )

    # -----------------------------------------------------
    # PERSONEN / BEZIEHUNGEN SPEICHERN
    # -----------------------------------------------------

    people_result = (
        process_people_analysis(
            answer,
            analysis,
        )
    )

    pending_candidates = (
        people_result[
            "pending_candidates"
        ]
    )

    # Falls aktuelle Antwort gerade eine alte
    # Identitätsfrage beantwortet hat:
    resolved_identity = (
        maybe_resolve_identity_from_followup(
            answer,
            analysis,
            current_user,
        )
    )

    # -----------------------------------------------------
    # PRIVACY
    # -----------------------------------------------------

    privacy_value = analysis.get(
        "privacy_signal",
        False,
    )

    if isinstance(
        privacy_value,
        bool,
    ):
        privacy_signal = (
            privacy_value
        )

    elif isinstance(
        privacy_value,
        str,
    ):
        privacy_signal = (
            privacy_value
            .strip()
            .lower()
            in {
                "true",
                "1",
                "yes",
                "ja",
            }
        )

    else:
        privacy_signal = bool(
            privacy_value
        )

    # -----------------------------------------------------
    # TIMELINE
    # -----------------------------------------------------

    (
        analyzed_year,
        analyzed_label,
        analyzed_confidence,
    ) = normalize_timeline(
        analysis.get(
            "timeline_year"
        ),
        analysis.get(
            "timeline_label"
        ),
        analysis.get(
            "timeline_confidence"
        ),
    )

    root_answer = get_root_answer(
        answer
    )

    is_follow_up = (
        str(root_answer["id"])
        != str(answer["id"])
    )

    timeline_year = analyzed_year
    timeline_label = analyzed_label
    timeline_confidence = (
        analyzed_confidence
    )

    if is_follow_up:
        root_year = root_answer.get(
            "timeline_year"
        )

        root_label = root_answer.get(
            "timeline_label"
        )

        root_confidence = (
            root_answer.get(
                "timeline_confidence"
            )
            or "unknown"
        )

        if root_year is not None:
            timeline_year = root_year

            timeline_label = (
                root_label
                or str(root_year)
            )

            timeline_confidence = (
                root_confidence
            )

            update_timeline_family(
                answer=answer,
                timeline_year=
                    timeline_year,
                timeline_label=
                    timeline_label
                    or None,
                timeline_confidence=
                    timeline_confidence,
            )

        elif analyzed_year is not None:
            update_timeline_family(
                answer=answer,
                timeline_year=
                    analyzed_year,
                timeline_label=
                    analyzed_label
                    or None,
                timeline_confidence=
                    analyzed_confidence,
            )

        else:
            timeline_year = None

            timeline_label = (
                root_label
                or ""
            )

            timeline_confidence = (
                root_confidence
            )

            update_timeline_family(
                answer=answer,
                timeline_year=None,
                timeline_label=
                    timeline_label
                    or None,
                timeline_confidence=
                    timeline_confidence,
            )

    elif (
        answer.get(
            "timeline_year"
        )
        is None
    ):
        update_timeline_family(
            answer=answer,
            timeline_year=
                analyzed_year,
            timeline_label=
                analyzed_label
                or None,
            timeline_confidence=
                analyzed_confidence,
        )

    else:
        # Bereits vorhandene Zeitangabe hat Vorrang.
        timeline_year = (
            answer.get(
                "timeline_year"
            )
        )

        timeline_label = (
            answer.get(
                "timeline_label"
            )
            or (
                str(timeline_year)
                if timeline_year
                is not None
                else ""
            )
        )

        timeline_confidence = (
            answer.get(
                "timeline_confidence"
            )
            or "unknown"
        )

    # -----------------------------------------------------
    # REANALYSE ERLEDIGT
    # -----------------------------------------------------

    (
        supabase
        .table("answers")
        .update(
            {
                "needs_reanalysis":
                    False,
            }
        )
        .eq(
            "id",
            answer_id,
        )
        .execute()
    )

    refreshed_answer = (
        get_answer_or_404(
            answer_id
        )
    )

    # Nach dem Speichern nochmal nur tatsächlich
    # noch offene Kandidaten laden.
    pending_result = (
        supabase
        .table(
            "person_identity_candidates"
        )
        .select("*")
        .eq(
            "answer_id",
            answer_id,
        )
        .eq(
            "status",
            "pending",
        )
        .order(
            "created_at"
        )
        .execute()
    )

    final_pending_candidates = (
        pending_result.data
        or []
    )

    # -----------------------------------------------------
    # 2. KI-CALL: NUR EMPATHISCHE FOLGEFRAGE
    # -----------------------------------------------------

    follow_up_question = (
        generate_follow_up_question(
            refreshed_answer,
            analysis,
            final_pending_candidates,
        )
    )

    # -----------------------------------------------------
    # ANTWORT
    # -----------------------------------------------------

    return {
        "status":
            "analyzed",

        "answer_id":
            answer_id,

        "memory":
            memory,

        "follow_up_question":
            follow_up_question,

        "privacy_signal":
            privacy_signal,

        "privacy_reason":
            clean_text(
                analysis.get(
                    "privacy_reason"
                )
            ),

        "timeline_year":
            timeline_year,

        "timeline_label":
            timeline_label,

        "timeline_confidence":
            timeline_confidence,

        "timeline_root_answer_id":
            root_answer["id"],

        "is_follow_up":
            is_follow_up,

        "people_created":
            people_result[
                "created_people"
            ],

        "identity_candidates":
            final_pending_candidates,

        "identity_resolved":
            resolved_identity,

        "needs_reanalysis":
            False,
    }