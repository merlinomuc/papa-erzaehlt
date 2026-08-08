import os
import json
import random
import subprocess
import tempfile
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
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
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


class FollowUpCreate(BaseModel):
    profile_id: str
    parent_answer_id: str
    text: str


class VisibilityUpdate(BaseModel):
    visibility: str


# =========================================================
# AUTH
# =========================================================

def get_current_app_user(
    authorization: str | None = Header(
        default=None
    )
):
    """
    Prüft:
    1. Bearer Token vorhanden?
    2. Supabase Auth akzeptiert Token?
    3. Benutzer existiert in app_users?
    """

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
            supabase.auth.get_user(
                token
            )
        )

        auth_user = auth_response.user

    except Exception as exc:
        print(
            "AUTH ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=401,
            detail="Session ist ungültig oder abgelaufen.",
        )


    if not auth_user:
        raise HTTPException(
            status_code=401,
            detail="Benutzer konnte nicht ermittelt werden.",
        )


    result = (
        supabase
        .table("app_users")
        .select(
            "id, auth_user_id, display_name, role, profile_id"
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
            detail="Dieser Benutzer ist nicht für die App freigeschaltet.",
        )


    app_user = result.data[0]

    app_user["email"] = (
        getattr(
            auth_user,
            "email",
            None,
        )
    )

    return app_user


def require_writer(
    current_user
):
    """
    Schreibzugriff:
    admin oder narrator.
    """

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
    """
    Admin darf jedes Profil benutzen.

    narrator darf ausschließlich
    das mit seinem Benutzer
    verbundene Profil benutzen.
    """

    require_writer(
        current_user
    )

    if current_user["role"] == "admin":
        return

    own_profile_id = (
        current_user.get(
            "profile_id"
        )
    )

    if (
        not own_profile_id
        or str(own_profile_id)
        != str(profile_id)
    ):
        raise HTTPException(
            status_code=403,
            detail="Dieses Profil gehört nicht zum angemeldeten Benutzer.",
        )


def get_answer_or_404(
    answer_id: str
):
    result = (
        supabase
        .table("answers")
        .select("*")
        .eq(
            "id",
            answer_id,
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Antwort nicht gefunden.",
        )

    return result.data[0]


def get_history_or_404(
    history_id: str
):
    result = (
        supabase
        .table("question_history")
        .select("*")
        .eq(
            "id",
            history_id,
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Fragenverlauf nicht gefunden.",
        )

    return result.data[0]


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


    if role == "admin":

        result = (
            supabase
            .table("profiles")
            .select("*")
            .order(
                "display_name"
            )
            .execute()
        )

        return result.data


    if role == "narrator":

        profile_id = (
            current_user.get(
                "profile_id"
            )
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


    if role == "reader":

        result = (
            supabase
            .table("profiles")
            .select("*")
            .order(
                "display_name"
            )
            .execute()
        )

        return result.data


    raise HTTPException(
        status_code=403,
        detail="Keine Berechtigung.",
    )


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
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
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
# FOLGEFRAGE SPEICHERN
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
            detail="Antwort gehört nicht zu diesem Profil.",
        )


    question_insert = (
        supabase
        .table("questions")
        .insert(
            {
                "text":
                    payload.text,

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
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
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
# FRAGE ALS BEANTWORTET MARKIEREN
# =========================================================

@app.post("/question/{history_id}/answered")
def question_answered(
    history_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):

    history = (
        get_history_or_404(
            history_id
        )
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
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
            }
        )
        .eq(
            "id",
            history_id,
        )
        .execute()
    )


    return {
        "status":
            "answered"
    }


# =========================================================
# FRAGE ÜBERSPRINGEN
# =========================================================

@app.post("/question/{history_id}/skipped")
def question_skipped(
    history_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):

    history = (
        get_history_or_404(
            history_id
        )
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
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
            }
        )
        .eq(
            "id",
            history_id,
        )
        .execute()
    )


    return {
        "status":
            "skipped"
    }


# =========================================================
# ANTWORT ANLEGEN
# =========================================================

@app.post("/answer")
def create_answer(
    answer: AnswerCreate,
    current_user=Depends(
        get_current_app_user
    ),
):

    history = (
        get_history_or_404(
            answer.history_id
        )
    )


    profile_id = (
        history["profile_id"]
    )


    authorize_profile(
        current_user,
        profile_id,
    )


    insert_result = (
        supabase
        .table("answers")
        .insert(
            {
                "profile_id":
                    profile_id,

                "session_id":
                    history.get(
                        "session_id"
                    ),

                "question_id":
                    history.get(
                        "question_id"
                    ),

                "original_transcript":
                    answer.text,

                "cleaned_transcript":
                    None,

                "visibility":
                    "all",

                "include_in_memoir":
                    False,

                "answered_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
            }
        )
        .execute()
    )


    created_answer = (
        insert_result.data[0]
    )


    (
        supabase
        .table("question_history")
        .update(
            {
                "status":
                    "answered",

                "answered_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
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
# SICHTBARKEIT
# =========================================================

@app.post("/answer/{answer_id}/visibility")
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
            detail="visibility muss 'family' oder 'all' sein.",
        )


    answer = (
        get_answer_or_404(
            answer_id
        )
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

    answer = (
        get_answer_or_404(
            answer_id
        )
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
        filename
        .rsplit(
            ".",
            1,
        )[-1]
        .lower()
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


    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Nicht unterstütztes Audioformat.",
        )


    file_bytes = (
        await audio.read()
    )


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
            .from_("memories-audio")
            .upload(
                storage_path,
                file_bytes,
                {
                    "content-type":
                        audio.content_type
                        or "application/octet-stream",

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
            detail="Audio konnte nicht gespeichert werden.",
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

@app.post("/answer/{answer_id}/transcribe")
def transcribe_answer(
    answer_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):

    answer = (
        get_answer_or_404(
            answer_id
        )
    )


    authorize_profile(
        current_user,
        answer["profile_id"],
    )


    audio_path = (
        answer.get(
            "audio_path"
        )
    )


    if not audio_path:
        raise HTTPException(
            status_code=400,
            detail="Für diese Antwort ist kein Audio gespeichert.",
        )


    try:

        audio_bytes = (
            supabase
            .storage
            .from_("memories-audio")
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
            detail="Audio konnte nicht aus dem Speicher geladen werden.",
        )


    original_extension = (
        audio_path
        .rsplit(
            ".",
            1,
        )[-1]
        .lower()
    )


    source_file = None
    wav_file = None


    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{original_extension}",
        ) as temp_source:

            temp_source.write(
                audio_bytes
            )

            source_file = (
                temp_source.name
            )


        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        ) as temp_wav:

            wav_file = (
                temp_wav.name
            )


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
                detail="Audio konnte nicht für die Transkription vorbereitet werden.",
            )


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


        transcript = (
            transcription.text
            or ""
        ).strip()


        (
            supabase
            .table("answers")
            .update(
                {
                    "original_transcript":
                        transcript
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
                "transcribed",

            "answer_id":
                answer_id,

            "transcript":
                transcript,
        }


    finally:

        for path in (
            source_file,
            wav_file,
        ):

            if (
                path
                and os.path.exists(
                    path
                )
            ):

                try:
                    os.remove(
                        path
                    )

                except OSError:
                    pass


# =========================================================
# ANALYSE
# =========================================================

@app.post("/answer/{answer_id}/analyze")
def analyze_answer(
    answer_id: str,
    current_user=Depends(
        get_current_app_user
    ),
):

    answer = (
        get_answer_or_404(
            answer_id
        )
    )


    authorize_profile(
        current_user,
        answer["profile_id"],
    )


    transcript = (
        answer.get(
            "original_transcript"
        )
        or ""
    ).strip()


    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Die Antwort enthält noch kein Transkript.",
        )


    question_text = ""


    question_id = (
        answer.get(
            "question_id"
        )
    )


    if question_id:

        question_result = (
            supabase
            .table("questions")
            .select(
                "text"
            )
            .eq(
                "id",
                question_id,
            )
            .limit(1)
            .execute()
        )


        if question_result.data:

            question_text = (
                question_result
                .data[0]
                .get(
                    "text",
                    ""
                )
            )


    prompt = f"""
Du analysierst eine persönliche Lebenserinnerung
für ein privates Familienarchiv.

Frage:
{question_text}

Antwort:
{transcript}

Antworte ausschließlich mit gültigem JSON.

Format:

{{
  "summary": "Kurze sachliche Zusammenfassung",
  "people": [],
  "places": [],
  "years": [],
  "topics": [],
  "keywords": [],
  "follow_up_question": "",
  "privacy_signal": false,
  "privacy_reason": ""
}}

Regeln:

summary:
Kurze Zusammenfassung der Erinnerung.
Keine neuen Tatsachen erfinden.

people:
Genannte Personen oder erkennbare Beziehungen,
zum Beispiel "Mutter", "Vater", "Bruder".

places:
Genannte Orte.

years:
Genannte Jahreszahlen oder klar erkennbare Zeitangaben.

topics:
Wichtige Themen.

keywords:
Wichtige Stichwörter.

follow_up_question:
Eine kurze, natürliche und respektvolle Nachfrage,
wenn sich aus der Antwort eine interessante
Vertiefung ergibt.
Wenn keine sinnvolle Nachfrage nötig ist,
leerer String.

PRIVACY:

privacy_signal = true NUR wenn die Person
klar ausdrückt, dass die Aussage vertraulich,
privat oder nicht für alle bestimmt sein soll.

Beispiele TRUE:
- "Das bleibt aber unter uns."
- "Das sage ich dir im Vertrauen."
- "Das soll nicht jeder wissen."
- "Bitte nicht öffentlich."
- "Das ist privat."
- "Das soll nur die Familie wissen."

Beispiele FALSE:
- "Das ist kein Geheimnis."
- "Das kann ruhig jeder wissen."
- "Das kannst du allen erzählen."
- bloß peinliche oder persönliche Inhalte ohne
  ausdrücklichen Wunsch nach Vertraulichkeit.

Bei Unsicherheit privacy_signal = false.

privacy_reason:
Wenn privacy_signal true ist:
kurze Erklärung, wodurch der Wunsch nach
Vertraulichkeit erkannt wurde.
Sonst leerer String.
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


        raw_text = (
            response.output_text
            or ""
        ).strip()


        if raw_text.startswith(
            "```"
        ):

            raw_text = raw_text.strip(
                "`"
            )

            if raw_text.startswith(
                "json"
            ):
                raw_text = (
                    raw_text[4:]
                    .strip()
                )


        analysis = json.loads(
            raw_text
        )


    except Exception as exc:

        print(
            "ANALYSIS ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="KI-Auswertung fehlgeschlagen.",
        )


    memory_payload = {
        "answer_id":
            answer_id,

        "summary":
            analysis.get(
                "summary",
                ""
            ),

        "people":
            analysis.get(
                "people",
                []
            ),

        "places":
            analysis.get(
                "places",
                []
            ),

        "years":
            analysis.get(
                "years",
                []
            ),

        "topics":
            analysis.get(
                "topics",
                []
            ),

        "keywords":
            analysis.get(
                "keywords",
                []
            ),
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


    privacy_value = (
        analysis.get(
            "privacy_signal",
            False
        )
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


    return {
        "status":
            "analyzed",

        "answer_id":
            answer_id,

        "memory":
            memory,

        "follow_up_question":
            analysis.get(
                "follow_up_question",
                ""
            ),

        "privacy_signal":
            privacy_signal,

        "privacy_reason":
            analysis.get(
                "privacy_reason",
                ""
            ),
    }