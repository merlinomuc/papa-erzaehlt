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

SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    "ffmpeg",
)

FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://127.0.0.1:5500",
)


if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL fehlt."
    )

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY fehlt."
    )

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY fehlt."
    )

if (
    FFMPEG_PATH != "ffmpeg"
    and not os.path.exists(
        FFMPEG_PATH
    )
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

    return str(
        value
    ).strip()


def parse_json_response(raw_text: str):
    text = clean_text(
        raw_text
    )

    if text.startswith("```"):
        text = text.strip("`").strip()

        if text.startswith("json"):
            text = (
                text[4:]
                .strip()
            )

    return json.loads(
        text
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
        or parts[0].lower()
        != "bearer"
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Ungültiger "
                "Authorization-Header."
            ),
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

        auth_user = (
            auth_response.user
        )

    except Exception as exc:
        print(
            "AUTH ERROR:",
            exc,
        )

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


def require_writer(
    current_user
):
    if current_user["role"] not in (
        "admin",
        "narrator",
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Keine Schreibberechtigung."
            ),
        )


def authorize_profile(
    current_user,
    profile_id: str,
):
    require_writer(
        current_user
    )

    if (
        current_user["role"]
        == "admin"
    ):
        return

    own_profile_id = (
        current_user.get(
            "profile_id"
        )
    )

    if (
        not own_profile_id
        or str(
            own_profile_id
        )
        != str(
            profile_id
        )
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
    role = (
        current_user["role"]
    )

    if role in (
        "admin",
        "reader",
    ):
        return

    if role == "narrator":
        own_profile_id = (
            current_user.get(
                "profile_id"
            )
        )

        if (
            own_profile_id
            and str(
                own_profile_id
            )
            == str(
                profile_id
            )
        ):
            return

    raise HTTPException(
        status_code=403,
        detail=(
            "Keine Leseberechtigung."
        ),
    )


# =========================================================
# DATENBANK-HILFSFUNKTIONEN
# =========================================================

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
            detail=(
                "Antwort nicht gefunden."
            ),
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
            detail=(
                "Fragenverlauf "
                "nicht gefunden."
            ),
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
        .eq(
            "id",
            question_id,
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


# =========================================================
# ERINNERUNGS-KETTEN
# =========================================================

def get_answer_chain(
    answer: dict
):
    """
    Liefert die komplette Kette von der
    ursprünglichen Erinnerung bis zur
    aktuellen Antwort.
    """

    chain = []
    current = answer
    visited = set()

    while current:
        current_id = str(
            current.get("id")
        )

        if current_id in visited:
            break

        visited.add(
            current_id
        )

        chain.append(
            current
        )

        question = (
            get_question_or_none(
                current.get(
                    "question_id"
                )
            )
        )

        if not question:
            break

        parent_answer_id = (
            question.get(
                "parent_answer_id"
            )
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

        current = (
            parent_result.data[0]
        )

    chain.reverse()

    return chain


def get_root_answer(
    answer: dict
):
    chain = get_answer_chain(
        answer
    )

    if chain:
        return chain[0]

    return answer


def get_timeline_family_answer_ids(
    root_answer_id: str
):
    """
    Sucht sämtliche Antworten,
    die über Folgefragen zu derselben
    Erinnerung gehören.
    """

    answer_ids = []
    queue = [
        root_answer_id
    ]
    seen = set()

    while queue:
        parent_answer_id = (
            queue.pop(0)
        )

        if parent_answer_id in seen:
            continue

        seen.add(
            parent_answer_id
        )

        answer_ids.append(
            parent_answer_id
        )

        questions_result = (
            supabase
            .table("questions")
            .select("id")
            .eq(
                "parent_answer_id",
                parent_answer_id,
            )
            .execute()
        )

        question_ids = [
            row["id"]

            for row in (
                questions_result.data
                or []
            )

            if row.get("id")
        ]

        if not question_ids:
            continue

        answers_result = (
            supabase
            .table("answers")
            .select("id")
            .in_(
                "question_id",
                question_ids,
            )
            .execute()
        )

        for row in (
            answers_result.data
            or []
        ):
            child_id = (
                row.get("id")
            )

            if (
                child_id
                and child_id not in seen
            ):
                queue.append(
                    child_id
                )

    return answer_ids


def update_timeline_family(
    answer: dict,
    timeline_year,
    timeline_label,
    timeline_confidence,
):
    root_answer = (
        get_root_answer(
            answer
        )
    )

    answer_ids = (
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

    if answer_ids:
        (
            supabase
            .table("answers")
            .update(
                update_data
            )
            .in_(
                "id",
                answer_ids,
            )
            .execute()
        )

    return (
        root_answer,
        answer_ids,
    )


# =========================================================
# KONTEXT DER ERINNERUNG
# =========================================================

def build_full_memory_context(
    answer: dict
):
    """
    Baut den kompletten Dialog dieser
    Erinnerung auf.

    Enthält auch die aktuelle Antwort.
    """

    chain = get_answer_chain(
        answer
    )

    blocks = []

    for index, item in enumerate(
        chain,
        start=1,
    ):
        question = (
            get_question_or_none(
                item.get(
                    "question_id"
                )
            )
        )

        question_text = ""

        if question:
            question_text = (
                clean_text(
                    question.get(
                        "text"
                    )
                )
            )

        transcript = (
            clean_text(
                item.get(
                    "original_transcript"
                )
            )
        )

        if question_text:
            block = (
                f"ABSCHNITT {index}\n"
                f"Frage: {question_text}\n"
                f"Antwort: {transcript}"
            )

        else:
            block = (
                f"ABSCHNITT {index}\n"
                f"Freie Erzählung: {transcript}"
            )

        blocks.append(
            block
        )

    if not blocks:
        return (
            "Noch keine Erinnerung vorhanden."
        )

    return "\n\n".join(
        blocks
    )


# =========================================================
# ZEIT NORMALISIEREN
# =========================================================

def normalize_timeline(
    year,
    label,
    confidence,
):
    if confidence not in (
        "exact",
        "approximate",
        "unknown",
    ):
        confidence = "unknown"

    if not isinstance(
        year,
        int,
    ):
        year = None

    if (
        year is not None
        and (
            year < 1800
            or year > 2100
        )
    ):
        year = None
        confidence = "unknown"

    label = clean_text(
        label
    )

    if (
        year is None
        and not label
    ):
        confidence = "unknown"

    return (
        year,
        label,
        confidence,
    )


# =========================================================
# EMPATHISCHE FOLGEFRAGE
# =========================================================

def generate_follow_up_question(
    answer: dict,
    analysis: dict,
):
    """
    Zweiter, eigenständiger KI-Aufruf.

    Dieser Aufruf hat NUR die Aufgabe,
    eine empathische und biografisch
    tiefgehende Folgefrage zu formulieren.
    """

    full_context = (
        build_full_memory_context(
            answer
        )
    )

    summary = clean_text(
        analysis.get(
            "summary",
            ""
        )
    )

    topics = (
        analysis.get(
            "topics",
            []
        )
        or []
    )

    people = (
        analysis.get(
            "people",
            []
        )
        or []
    )

    places = (
        analysis.get(
            "places",
            []
        )
        or []
    )

    prompt = f"""
Du führst ein ruhiges, warmes und sehr aufmerksames
biografisches Gespräch mit einem älteren Menschen.

Deine EINZIGE Aufgabe ist jetzt:

Nach der bisherigen Erzählung eine kurze,
menschliche Reaktion und – nur wenn sinnvoll –
eine einzige wirklich gute Folgefrage zu formulieren.

Du sollst NICHT analysieren.
Du sollst NICHT zusammenfassen.
Du sollst NICHT möglichst viele Informationen sammeln.

Du sollst eine Tür öffnen, durch die der Erzähler,
wenn er möchte, freiwillig tiefer in seine eigene
Lebenserinnerung eintreten kann.


==================================================
BISHERIGE GESAMTE ERINNERUNG
==================================================

{full_context}


==================================================
BISHERIGE ANALYSE
==================================================

Kurze Zusammenfassung:
{summary}

Themen:
{json.dumps(topics, ensure_ascii=False)}

Menschen:
{json.dumps(people, ensure_ascii=False)}

Orte:
{json.dumps(places, ensure_ascii=False)}


==================================================
DAS WICHTIGSTE ZIEL
==================================================

Suche nach der MENSCHLICHEN BEDEUTUNG hinter
der Erzählung.

Ein erwähnter Gegenstand, ein Geräusch, ein Zimmer,
ein Vorhang, ein Auto, ein Haus, ein Kleidungsstück,
ein Möbelstück oder irgendein anderes Detail ist
normalerweise NICHT das eigentliche Thema.

Solche Details sind oft nur Türen zu:

- einer Beziehung
- einem Gefühl
- einer Lebensphase
- Geborgenheit
- Angst
- Verlust
- Liebe
- Stolz
- Scham
- Hoffnung
- Einsamkeit
- Freiheit
- Verantwortung
- einer Entscheidung
- einem Wendepunkt
- einer Sehnsucht
- einem späteren Verständnis
- einer Veränderung im Leben
- einer persönlichen Haltung

Suche nach dieser tieferen Ebene.


==================================================
EXTREM WICHTIG:
NICHT AM OBERFLÄCHENDETAIL HÄNGEN BLEIBEN
==================================================

Beispiel:

Erzähler:
"Ich erinnere mich noch an die Vorhänge
in unserem Kinderzimmer."

SCHLECHT:
"Welche Farbe hatten die Vorhänge?"

SCHLECHT:
"Wie sahen die Vorhänge aus?"

SCHLECHT:
"Aus welchem Stoff waren sie?"

BESSER:
"Dass dir gerade dieses Zimmer so deutlich
in Erinnerung geblieben ist, ist bemerkenswert.
Was verbindest du heute mit der Zeit,
in der du dort gelebt hast?"

Oder:

"Wenn du an dieses Kinderzimmer zurückdenkst:
War das für dich damals eher ein Ort der
Geborgenheit oder verbindest du ganz andere
Gefühle damit?"

Diese zweite Variante nur verwenden,
wenn sie nicht suggestiv etwas behauptet.


Beispiel:

Erzähler:
"Ich erinnere mich an das Lachen meiner Mutter."

SCHLECHT:
"Wie klang das Lachen?"

SCHLECHT:
"War es laut?"

BESSER:
"Dass dir gerade ihr Lachen geblieben ist,
scheint etwas Besonderes zu sein.
Was bedeutete deine Mutter damals für dich?"


Beispiel:

Erzähler:
"Wir hatten damals einen roten Opel."

SCHLECHT:
"Welches Modell war der Opel?"

BESSER:
"Wenn du an diese Zeit mit dem Auto zurückdenkst:
Wofür stand es damals für euch – Freiheit,
Familie, Aufbruch oder etwas ganz anderes?"

Aber nur, wenn diese Richtung wirklich
zur bisherigen Erzählung passt.


==================================================
PRIORITÄTEN FÜR TIEFE
==================================================

Suche möglichst in dieser Reihenfolge nach
einer noch NICHT erzählten Ebene:


1. PERSÖNLICHE BEDEUTUNG

Warum ist gerade diese Erinnerung
bis heute geblieben?

Was bedeutet sie für den Erzähler?


2. BEZIEHUNGEN

Was bedeutete eine genannte Person für ihn?

Wie war die Beziehung wirklich?

Gab es Nähe, Distanz, Bewunderung,
Spannung, Abhängigkeit oder Vertrauen?

NICHTS davon unterstellen.
Nur vorsichtig danach fragen,
wenn sich die Beziehung als wichtig zeigt.


3. INNERE ERFAHRUNG

Was hat die Situation innerlich mit ihm gemacht?

Was dachte er damals?

Was war schwierig?

Was gab ihm Kraft?

Was machte ihn stolz?

Was hat ihn geprägt?

Nur fragen, wenn die Antwort noch
nicht bereits erzählt wurde.


4. WENDEPUNKTE

Gab es einen Moment,
nach dem etwas anders war?

Hat sich eine Haltung verändert?

Musste er eine Entscheidung treffen?


5. IDENTITÄT

Was hat diese Erfahrung aus seiner Sicht
mit dem Menschen zu tun,
der er später geworden ist?


6. SPÄTERES VERSTEHEN

Hat er erst später verstanden,
was damals wirklich passiert ist
oder was es für ihn bedeutet hat?


7. HEUTIGER BLICK

Sieht er die Situation heute anders
als damals?

Würde er heute etwas anders machen?

Was würde er seinem damaligen Ich sagen?

Diese Richtung sparsam verwenden.


8. UNGESAGTES

Gab es etwas,
worüber damals nicht gesprochen wurde?

Gab es Gefühle oder Gedanken,
die man für sich behalten musste?

Nur wenn die Erzählung tatsächlich
eine solche Ebene nahelegt.


9. VERLUST, BEDAUERN, STOLZ, LIEBE,
   HOFFNUNG ODER VERSÖHNUNG

Nur wenn diese Ebene wirklich
aus der Erinnerung hervorgeht.

Nicht künstlich hineininterpretieren.


10. KONKRETE SZENE

Nur wenn eine konkrete Szene wahrscheinlich
eine emotionale oder biografische Bedeutung
öffnet.

Die Szene ist Mittel zum Zweck,
nicht das eigentliche Ziel.


==================================================
WIEDERHOLUNGSVERBOT
==================================================

Du hast oben die GESAMTE bisherige Erinnerung.

Lies sie vollständig.

Frage NIEMALS nach etwas,
das bereits beantwortet wurde.

Frage auch nicht dasselbe
mit anderen Worten.

Wenn bereits erzählt wurde,
wie sich etwas angefühlt hat,
frage NICHT noch einmal:

"Wie hast du dich dabei gefühlt?"

Wenn bereits die Beziehung zur Mutter
ausführlich beschrieben wurde,
frage NICHT erneut nach dieser Beziehung.

Wenn bereits erklärt wurde,
warum eine Entscheidung getroffen wurde,
frage NICHT erneut nach dem Grund.

Wenn eine Ebene bereits erzählt wurde,
suche die nächste noch offene Ebene.


==================================================
EMPATHISCHE REAKTION
==================================================

Bevor die eigentliche Frage kommt,
DARF ein kurzer empathischer Satz stehen.

Meistens ein Satz.

Nie mehr als zwei sehr kurze Sätze.

Beispiele:

"Das klingt nach einer wirklich schweren Zeit."

"Das scheint dir bis heute viel zu bedeuten."

"Das klingt nach einer sehr schönen Erinnerung."

"Da steckt offenbar viel Erinnerung drin."

"Das muss ein ziemlich einschneidender Moment
gewesen sein."

"Dass dir gerade dieser Augenblick geblieben ist,
ist bemerkenswert."

"Das klingt nach einer Zeit,
die dich sehr geprägt haben könnte."


Aber:

Behaupte niemals ein Gefühl als Tatsache,
wenn der Erzähler es nicht selbst gesagt hat.

SCHLECHT:

"Du warst bestimmt völlig verzweifelt."

SCHLECHT:

"Das hat dich traumatisiert."

SCHLECHT:

"Du hast dich sicher ungeliebt gefühlt."


BESSER:

"Das klingt nach einer sehr schwierigen Situation."

Oder:

"Das könnte eine ziemlich belastende Zeit
gewesen sein."


==================================================
MEHR EMOTIONALER KONTAKT
==================================================

Die Antwort darf warm und menschlich sein.

Sie darf zeigen:

"Ich habe verstanden,
dass das für dich wichtig ist."

Sie darf Anteilnahme zeigen.

Sie darf auch einmal sagen:

"Oh je, das klingt wirklich nach
einer schweren Situation."

Aber solche Formulierungen nur selten
und nur wenn sie wirklich passen.

Nicht jede Antwort mit:

"Das klingt ..."

beginnen.

Variiere natürlich.


==================================================
EMOJIS
==================================================

Emojis sind erlaubt,
aber wirklich nur sehr selten.

Normalfall:
KEIN Emoji.

Wenn ein Emoji die kurze menschliche Reaktion
wirklich natürlicher macht,
darf GENAU EIN Emoji verwendet werden.

Erlaubt sind ausschließlich:

🙂
😔
❤️
😮

Keine anderen Emojis.

Keine Emoji-Ketten.

Kein Emoji am Ende jeder Nachricht.

Bei besonders ernsten Themen wie:

- Tod
- Krieg
- schwere Krankheit
- Gewalt
- Trauma
- sehr intime Erinnerungen
- Missbrauch
- große Verluste

im Zweifel KEIN Emoji verwenden.

Die Würde der Erzählung ist wichtiger
als ein Emoji.


==================================================
PERSÖNLICHE FRAGEN SIND ERLAUBT
==================================================

Du darfst tiefer fragen.

Du darfst zum Beispiel fragen:

"Was hat das damals mit dir gemacht?"

Aber NUR,
wenn diese emotionale Ebene noch nicht
ausführlich erzählt wurde.

Du darfst fragen:

"Was glaubst du heute:
Warum ist dir gerade dieser Moment
so deutlich geblieben?"

Du darfst fragen:

"Wenn du heute darauf zurückblickst:
Was hat diese Erfahrung in deinem Leben verändert?"

Du darfst fragen:

"Gab es damals etwas,
das du niemandem gesagt hast?"

Aber nur,
wenn die bisherige Erinnerung dafür
einen echten Anlass gibt.

Du darfst fragen:

"Was bedeutete dieser Mensch wirklich für dich?"

Du darfst fragen:

"Was war damals vielleicht schwieriger,
als die Menschen um dich herum gemerkt haben?"

Aber nur,
wenn das nicht einfach frei erfunden
oder unpassend ist.


==================================================
FREIWILLIGKEIT
==================================================

Der Erzähler entscheidet immer selbst,
wie tief er gehen möchte.

Bei einer besonders persönlichen Frage
kannst du gelegentlich sagen:

"Wenn du darüber erzählen möchtest ..."

"Falls du das erzählen magst ..."

"Wenn du dich daran erinnern möchtest ..."

"Nur wenn du darüber sprechen möchtest ..."

Aber nicht mechanisch bei jeder Frage.


==================================================
KEIN THERAPIEGESPRÄCH
==================================================

Du bist kein Psychotherapeut.

Keine Diagnose.

Keine Traumadeutung.

Keine Behandlung.

Keine Psychoanalyse.

Keine Behauptung über unbewusste Motive.

Keine Aussagen wie:

"Das liegt bestimmt daran, dass ..."

Du darfst psychologisch interessante
biografische Fragen stellen,
aber der Erzähler selbst liefert die Bedeutung.


==================================================
DIE BESTE FRAGE
==================================================

Bevor du antwortest,
überlege intern mehrere mögliche Fragen.

Prüfe jede davon:

1. Ist sie bereits beantwortet?

2. Ist sie nur ein belangloses Detail?

3. Öffnet sie wirklich eine neue Ebene?

4. Könnte daraus eine Geschichte entstehen?

5. Hat sie biografische Bedeutung?

6. Ist sie menschlich und respektvoll?

7. Würde ein aufmerksamer Gesprächspartner
   diese Frage tatsächlich stellen?

Wähle nur die beste Frage.

Gib deine Überlegungen NICHT aus.


==================================================
QUALITÄT VOR MENGE
==================================================

Es muss NICHT nach jeder Erinnerung
eine Folgefrage geben.

Wenn die Geschichte bereits rund ist,

oder keine neue bedeutungsvolle Ebene
offen ist,

oder dir nur eine Wiederholung einfällt,

dann gib einen leeren String zurück.


==================================================
AUSGABE
==================================================

Antworte ausschließlich mit gültigem JSON.

Exakt dieses Format:

{{
  "follow_up_question": ""
}}

Wenn eine sinnvolle Frage vorhanden ist,
enthält follow_up_question:

eine kurze empathische Reaktion
plus eine einzige vertiefende Frage.

Beispiel:

{{
  "follow_up_question":
  "Das klingt nach einer Zeit, die dir bis heute sehr nahe ist. Wenn du darüber erzählen möchtest: Was hat diese Erfahrung später in deinem Leben verändert?"
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

        follow_up_question = (
            clean_text(
                result.get(
                    "follow_up_question",
                    ""
                )
            )
        )

        if (
            follow_up_question
            and len(
                follow_up_question
            ) < 15
        ):
            return ""

        return follow_up_question

    except Exception as exc:
        # -------------------------------------------------
        # WICHTIG:
        #
        # Wenn nur die Folgefrage fehlschlägt,
        # darf die eigentliche Erinnerung trotzdem
        # gespeichert werden.
        # -------------------------------------------------

        print(
            "FOLLOW-UP GENERATION ERROR:",
            exc,
        )

        return ""


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
            current_user[
                "auth_user_id"
            ],

        "display_name":
            current_user[
                "display_name"
            ],

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
    role = (
        current_user["role"]
    )

    if role in (
        "admin",
        "reader",
    ):
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

    raise HTTPException(
        status_code=403,
        detail=(
            "Keine Berechtigung."
        ),
    )


# =========================================================
# ARCHIV / ERINNERUNGEN
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
            "original_transcript, visibility, "
            "audio_path, answered_at, created_at, "
            "timeline_year, timeline_label, "
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
        row["answer_id"]:
            row

        for row in (
            memories_result.data
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
            row["id"]:
                row

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
            question = (
                question_map.get(
                    answer[
                        "question_id"
                    ]
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
                    answer.get(
                        "original_transcript"
                    )
                    or "",

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
        "items":
            items
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
    answer = (
        get_answer_or_404(
            answer_id
        )
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
            payload.timeline_year
            < 1800
            or payload.timeline_year
            > 2100
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
        payload.timeline_label.strip()
        if payload.timeline_label
        else None
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

    (
        root_answer,
        answer_ids,
    ) = update_timeline_family(
        answer=answer,
        timeline_year=
            payload.timeline_year,
        timeline_label=
            label,
        timeline_confidence=
            confidence,
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

        "timeline_root_answer_id":
            root_answer["id"],

        "updated_answer_ids":
            answer_ids,
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
            detail=(
                "Profil nicht gefunden."
            ),
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
            detail=(
                "Keine Fragen vorhanden."
            ),
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
# FOLGEFRAGE ANLEGEN
# =========================================================

@app.post(
    "/question/follow-up"
)
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
            detail=(
                "Antwort gehört nicht "
                "zu diesem Profil."
            ),
        )

    follow_up_text = (
        clean_text(
            payload.text
        )
    )

    if not follow_up_text:
        raise HTTPException(
            status_code=400,
            detail=(
                "Die Folgefrage ist leer."
            ),
        )

    question_insert = (
        supabase
        .table("questions")
        .insert(
            {
                "text":
                    follow_up_text,

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
# FRAGE BEANTWORTET
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
        "status":
            "answered"
    }


# =========================================================
# FRAGE ÜBERSPRINGEN
# =========================================================

@app.post(
    "/question/{history_id}/skipped"
)
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
        "status":
            "skipped"
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

    question_id = (
        history.get(
            "question_id"
        )
    )

    question = (
        get_question_or_none(
            question_id
        )
    )

    timeline_year = None
    timeline_label = None
    timeline_confidence = (
        "unknown"
    )

    # -----------------------------------------------------
    # Folgeantwort übernimmt sofort die Zeit
    # der ursprünglichen Erinnerung.
    # -----------------------------------------------------

    if (
        question
        and question.get(
            "parent_answer_id"
        )
    ):
        parent_answer = (
            get_answer_or_404(
                question[
                    "parent_answer_id"
                ]
            )
        )

        root_answer = (
            get_root_answer(
                parent_answer
            )
        )

        timeline_year = (
            root_answer.get(
                "timeline_year"
            )
        )

        timeline_label = (
            root_answer.get(
                "timeline_label"
            )
        )

        timeline_confidence = (
            root_answer.get(
                "timeline_confidence"
            )
            or "unknown"
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
                    question_id,

                "original_transcript":
                    answer.text,

                "cleaned_transcript":
                    None,

                "visibility":
                    "all",

                "include_in_memoir":
                    False,

                "answered_at":
                    utc_now_iso(),

                "timeline_year":
                    timeline_year,

                "timeline_label":
                    timeline_label,

                "timeline_confidence":
                    timeline_confidence,
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
    answer = (
        get_answer_or_404(
            answer_id
        )
    )

    authorize_profile(
        current_user,
        answer["profile_id"],
    )

    history = None

    if payload.history_id:
        history = (
            get_history_or_404(
                payload.history_id
            )
        )

        if (
            str(
                history[
                    "profile_id"
                ]
            )
            != str(
                answer[
                    "profile_id"
                ]
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Frage und Antwort "
                    "gehören nicht zusammen."
                ),
            )

    audio_path = (
        answer.get(
            "audio_path"
        )
    )

    if audio_path:
        try:
            (
                supabase
                .storage
                .from_(
                    "memories-audio"
                )
                .remove(
                    [audio_path]
                )
            )

        except Exception as exc:
            print(
                "AUDIO DELETE WARNING:",
                exc,
            )

    try:
        (
            supabase
            .table("memories")
            .delete()
            .eq(
                "answer_id",
                answer_id,
            )
            .execute()
        )

    except Exception as exc:
        print(
            "MEMORY DELETE WARNING:",
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
            .table("question_history")
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

    if (
        extension
        not in allowed_extensions
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Nicht unterstütztes "
                "Audioformat."
            ),
        )

    file_bytes = (
        await audio.read()
    )

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Audiodatei ist leer."
            ),
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

        if (
            process.returncode
            != 0
        ):
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

@app.post(
    "/answer/{answer_id}/analyze"
)
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
            detail=(
                "Die Antwort enthält "
                "noch kein Transkript."
            ),
        )

    question_id = (
        answer.get(
            "question_id"
        )
    )

    question = (
        get_question_or_none(
            question_id
        )
    )

    question_text = ""

    if question:
        question_text = (
            clean_text(
                question.get(
                    "text"
                )
            )
        )

    if question_text:
        context_text = f"""
Frage:
{question_text}
"""
    else:
        context_text = """
Es handelt sich um eine freie Erinnerung.
Es wurde vorher keine Frage gestellt.
"""

    # =====================================================
    # KI 1:
    # ARCHIVIERUNG / STRUKTURIERUNG
    # =====================================================

    analysis_prompt = f"""
Du analysierst eine persönliche Lebenserinnerung
für ein privates Familienarchiv.

{context_text}

Erzählung:

{transcript}

Antworte ausschließlich mit gültigem JSON.

Format:

{{
  "summary": "Kurze natürliche Zusammenfassung",
  "people": [],
  "places": [],
  "years": [],
  "topics": [],
  "keywords": [],
  "privacy_signal": false,
  "privacy_reason": "",
  "timeline_year": null,
  "timeline_label": "",
  "timeline_confidence": "unknown"
}}


==================================================
ZUSAMMENFASSUNG
==================================================

summary:

Kurze, natürliche und respektvolle
Zusammenfassung.

Keine neuen Tatsachen erfinden.

Keine psychologische Diagnose.


people:

Genannte Personen oder Beziehungen.


places:

Genannte Orte.


years:

Im Text tatsächlich genannte Jahreszahlen
oder klare Zeitangaben.


topics:

Wichtige Themen.


keywords:

Wichtige Stichwörter.


==================================================
ZEITLEISTE
==================================================

timeline_year:

Nur eine vierstellige Jahreszahl,
wenn sich aus der Erzählung selbst
ein sinnvolles Jahr ergibt.


timeline_label:

Natürliche Bezeichnung wie:

"1945"

"etwa 1950"

"Sommer 1962"


timeline_confidence:

"exact",
wenn das Jahr klar genannt wurde.

"approximate",
wenn die Person selbst ungefähr
ein Jahr nennt.

"unknown",
wenn kein belastbares Jahr vorhanden ist.


WICHTIG:

Keine historischen Jahreszahlen
aus deinem Weltwissen ergänzen.

Keine Jahreszahl erraten.

Keine Jahreszahl aus bekannten
historischen Ereignissen ableiten.

Bei Unsicherheit:

timeline_year = null

timeline_confidence = "unknown"


==================================================
PRIVACY
==================================================

privacy_signal = true NUR wenn die Person
klar ausdrückt, dass die Aussage vertraulich
oder nicht für alle bestimmt sein soll.

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
- Persönliche Inhalte ohne ausdrücklichen
  Vertraulichkeitswunsch.

Bei Unsicherheit false.

privacy_reason:

Bei true kurze sachliche Erklärung.

Sonst leer.
"""

    try:
        analysis_response = (
            openai_client
            .responses
            .create(
                model="gpt-5-mini",
                input=analysis_prompt,
            )
        )

        analysis = (
            parse_json_response(
                analysis_response.output_text
                or ""
            )
        )

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


    # =====================================================
    # MEMORY SPEICHERN
    # =====================================================

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
            on_conflict=
                "answer_id",
        )
        .execute()
    )

    memory = (
        memory_result.data[0]

        if memory_result.data

        else memory_payload
    )


    # =====================================================
    # PRIVACY NORMALISIEREN
    # =====================================================

    privacy_value = (
        analysis.get(
            "privacy_signal",
            False,
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
        privacy_signal = (
            bool(
                privacy_value
            )
        )


    # =====================================================
    # ZEIT NORMALISIEREN
    # =====================================================

    (
        analyzed_year,
        analyzed_label,
        analyzed_confidence,
    ) = normalize_timeline(
        analysis.get(
            "timeline_year"
        ),

        analysis.get(
            "timeline_label",
            ""
        ),

        analysis.get(
            "timeline_confidence",
            "unknown"
        )
        or "unknown",
    )

    root_answer = (
        get_root_answer(
            answer
        )
    )

    is_follow_up_answer = (
        str(
            root_answer["id"]
        )
        != str(
            answer["id"]
        )
    )


    # =====================================================
    # ZEITLOGIK BEI FOLGEFRAGEN
    # =====================================================

    if is_follow_up_answer:
        root_year = (
            root_answer.get(
                "timeline_year"
            )
        )

        root_label = (
            root_answer.get(
                "timeline_label"
            )
        )

        root_confidence = (
            root_answer.get(
                "timeline_confidence"
            )
            or "unknown"
        )

        if root_year is not None:
            final_year = (
                root_year
            )

            final_label = (
                root_label
                or str(
                    root_year
                )
            )

            final_confidence = (
                root_confidence
            )

            update_timeline_family(
                answer=
                    answer,

                timeline_year=
                    final_year,

                timeline_label=
                    final_label,

                timeline_confidence=
                    final_confidence,
            )

        elif analyzed_year is not None:
            final_year = (
                analyzed_year
            )

            final_label = (
                analyzed_label
                or str(
                    analyzed_year
                )
            )

            final_confidence = (
                analyzed_confidence
            )

            update_timeline_family(
                answer=
                    answer,

                timeline_year=
                    final_year,

                timeline_label=
                    final_label,

                timeline_confidence=
                    final_confidence,
            )

        else:
            final_year = None

            final_label = (
                root_label
                or ""
            )

            final_confidence = (
                root_confidence
                or "unknown"
            )

            update_timeline_family(
                answer=
                    answer,

                timeline_year=
                    None,

                timeline_label=
                    (
                        final_label
                        or None
                    ),

                timeline_confidence=
                    final_confidence,
            )


    # =====================================================
    # ZEITLOGIK HAUPTERINNERUNG
    # =====================================================

    else:
        existing_year = (
            answer.get(
                "timeline_year"
            )
        )

        if existing_year is None:
            final_year = (
                analyzed_year
            )

            final_label = (
                analyzed_label
            )

            final_confidence = (
                analyzed_confidence
            )

            update_timeline_family(
                answer=
                    answer,

                timeline_year=
                    final_year,

                timeline_label=
                    (
                        final_label
                        or None
                    ),

                timeline_confidence=
                    final_confidence,
            )

        else:
            final_year = (
                existing_year
            )

            final_label = (
                answer.get(
                    "timeline_label"
                )
                or str(
                    existing_year
                )
            )

            final_confidence = (
                answer.get(
                    "timeline_confidence"
                )
                or "unknown"
            )


    # =====================================================
    # KI 2:
    # EMPATHISCHE, TIEFE FOLGEFRAGE
    # =====================================================

    # Antwort nochmals laden,
    # damit der komplette aktuelle Zustand
    # für die Erinnerungskette vorhanden ist.

    refreshed_answer = (
        get_answer_or_404(
            answer_id
        )
    )

    follow_up_question = (
        generate_follow_up_question(
            refreshed_answer,
            analysis,
        )
    )


    # =====================================================
    # RESPONSE
    # =====================================================

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
            analysis.get(
                "privacy_reason",
                ""
            ),

        "timeline_year":
            final_year,

        "timeline_label":
            final_label,

        "timeline_confidence":
            final_confidence,

        "timeline_root_answer_id":
            root_answer["id"],

        "is_follow_up":
            is_follow_up_answer,
    }