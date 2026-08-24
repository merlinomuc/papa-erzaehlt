LOGIN-RECOVERY V4

Diese Version basiert auf der zuvor funktionierenden V2 mit Fortschrittsanzeige.
Der globale Login-/apiFetch-Code wurde NICHT verändert.
Nur unmittelbar vor PDF/DOCX-Export und Archiv-Backup wird die Supabase-Session erneuert.
Damit wird der Login-Rückfall aus V3 entfernt, ohne den ursprünglichen PDF-Sessionfehler unbehandelt zu lassen.
PWA-Cache: v7.
