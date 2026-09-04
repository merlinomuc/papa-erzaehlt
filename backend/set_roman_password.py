from __future__ import annotations

import os
import sys
from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


ROMAN_USER_ID = "cb76bf98-6c02-4a30-aef3-5cc66a017ea4"
ROMAN_EMAIL = "romdede@gmx.de"


def load_configuration() -> tuple[str, str]:
    script_dir = Path(__file__).resolve().parent
    env_file = script_dir / ".env"

    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()

    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    service_role_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL fehlt. Bitte prüfe deine backend/.env-Datei."
        )

    if not service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY fehlt. "
            "Bitte prüfe deine backend/.env-Datei."
        )

    return supabase_url, service_role_key


def read_new_password() -> str:
    print()
    print("Neues Passwort für Roman festlegen")
    print("----------------------------------")
    print(
        "Das Passwort wird beim Tippen nicht angezeigt. "
        "Das ist absichtlich so."
    )
    print()

    password_1 = getpass("Neues Passwort: ")
    password_2 = getpass("Passwort wiederholen: ")

    if password_1 != password_2:
        raise ValueError("Die beiden Passwörter stimmen nicht überein.")

    if len(password_1) < 8:
        raise ValueError(
            "Bitte ein Passwort mit mindestens 8 Zeichen verwenden."
        )

    return password_1


def main() -> int:
    print("=" * 58)
    print("Romans Passwort einmalig neu setzen")
    print("=" * 58)
    print()
    print(f"Benutzer: {ROMAN_EMAIL}")
    print(f"User-ID:  {ROMAN_USER_ID}")
    print()
    print(
        "Dieses Skript ändert ausschließlich das Passwort dieses "
        "bestehenden Supabase-Auth-Benutzers."
    )

    try:
        supabase_url, service_role_key = load_configuration()
        new_password = read_new_password()

        confirm = input(
            "\nPasswort für Roman jetzt wirklich ändern? [j/N]: "
        ).strip().lower()

        if confirm not in {"j", "ja", "y", "yes"}:
            print("\nAbgebrochen. Es wurde nichts geändert.")
            return 0

        client = create_client(
            supabase_url,
            service_role_key,
        )

        response = client.auth.admin.update_user_by_id(
            ROMAN_USER_ID,
            {
                "password": new_password,
            },
        )

        user = getattr(response, "user", None)

        if user is None:
            print()
            print(
                "Supabase hat keine Benutzerinformation zurückgegeben. "
                "Bitte im Dashboard prüfen, ob die Änderung übernommen wurde."
            )
            return 1

        returned_email = getattr(user, "email", None)

        print()
        print("ERFOLG")
        print("------")
        print("Romans Passwort wurde in Supabase neu gesetzt.")

        if returned_email:
            print(f"Bestätigter Benutzer: {returned_email}")

        print()
        print(
            "Bitte jetzt einmal direkt in der App mit Romans E-Mail "
            "und dem neuen Passwort anmelden."
        )
        print()
        print("Danach kannst du diese Datei wieder löschen.")

        return 0

    except KeyboardInterrupt:
        print("\n\nAbgebrochen. Es wurde nichts geändert.")
        return 1
    except Exception as exc:
        print()
        print("FEHLER")
        print("------")
        print(str(exc))
        print()
        print("Es wurde kein Passwort im Klartext ausgegeben.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
