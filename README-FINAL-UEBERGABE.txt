ROMANS ERINNERUNGEN – FINALE UEBERGABEVERSION
Stand: 24.08.2026

NEU IN DIESER VERSION
=====================
1. "Mein Buch" ist fuer Roman UND den Admin sichtbar.
2. Zwei Memoiren-Fassungen:
   - Komplette Memoiren / Familienfassung:
     verwendet auch Erinnerungen mit "Nur Familie".
   - Version zum Teilen:
     verwendet nur Erinnerungen mit "Fuer alle".
3. Vor dem Export wird eine Buchvorschau mit Kapiteln gezeigt.
4. Export als PDF im Buchformat A5.
5. Export als bearbeitbare Word-Datei (.docx).
6. Komplettes Archiv als ZIP sichern:
   Erinnerungen + Personen + vorhandene Original-/Ergaenzungs-Audios.
7. In einer geoeffneten Erinnerung kann die Originalaufnahme angehoert
   oder gespeichert werden.

DATENBANK
=========
Fuer diese Erweiterung ist KEINE neue SQL-Migration notwendig.
Die bestehende visibility-Logik (all/family) wird verwendet.

BACKEND-ABHAENGIGKEITEN
=======================
requirements.txt enthaelt zusaetzlich:
- reportlab (PDF)
- python-docx (Word)

DEPLOYMENT
==========
1. Den Inhalt dieses Ordners in das bestehende GitHub-Repository uebernehmen.
2. NICHT die lokale .env-Datei ins Repository committen.
3. Commit + Push auf main.
4. Render Backend neu deployen lassen.
5. Render Frontend neu deployen lassen.
6. Auf dem Handy/Tablet die PWA einmal komplett schliessen und neu oeffnen.
   Der Service-Worker-Cache wurde auf v4 erhoeht.

KURZER TEST NACH DEM DEPLOYMENT
===============================
- Login als Roman.
- "Mein Buch" unten links oeffnen.
- Erinnerungszaehler pruefen.
- Familienfassung erstellen.
- Vorschau pruefen.
- PDF herunterladen.
- Word-Datei herunterladen.
- Teilbare Fassung erstellen und pruefen, dass "Nur Familie" nicht verwendet wird.
- Archiv-ZIP herunterladen.
- Eine Erinnerung mit Audio oeffnen und Originalaufnahme anhoeren.
- Normale Aufnahme, Transkript, Korrektur, Speichern und Folgefrage einmal testen.

HINWEIS ZU MEMOIREN
====================
Die Memoiren werden aus den tatsaechlich gespeicherten Erinnerungen erzeugt.
Die KI ist angewiesen, keine historischen Details, Gefuehle, Beziehungen oder
Jahreszahlen zu erfinden. Bei vielen Erinnerungen kann die Erstellung einige
Minuten dauern.
