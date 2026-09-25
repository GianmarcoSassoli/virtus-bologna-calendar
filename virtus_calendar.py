#!/usr/bin/env python3
"""
Calendario Virtus Bologna (LBA + EuroLeague) in formato iCalendar (.ics).

Scarica le partite dai dati ufficiali:
  - LBA:       https://www.legabasket.it (API interna usata dal sito)
  - EuroLeague: feed ufficiale usato da euroleaguebasketball.net

e genera tre file:
  virtus.ics             -> tutte le partite
  virtus-lba.ics         -> solo LBA (campionato, playoff, Coppa Italia, Supercoppa)
  virtus-euroleague.ics  -> solo EuroLeague

Nessuna dipendenza esterna: solo libreria standard di Python (3.11+).

Uso:  python virtus_calendar.py --out docs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# Configurazione
# --------------------------------------------------------------------------- #

LBA_BASE = "https://www.legabasket.it/api"
LBA_CLUB_CODE = "BOL"          # codice club Virtus in LBA (stabile tra le stagioni)
LBA_NAME_HINT = "virtus"       # controllo extra sul nome (il nome cambia con lo sponsor)
# Serie di competizioni LBA da includere: 1 = Serie A (RS + Playoff),
# 5 = Coppa Italia / Final Eight, 6 = Supercoppa. (21 = Next Gen, esclusa)
LBA_SERIES = {1, 5, 6}

# Icona a inizio titolo per competizione
ICON_SERIE_A = "🇮🇹"   # campionato e playoff Serie A
ICON_COPPA = "🏆"      # Coppa Italia e Supercoppa
ICON_EL = "🇪🇺"        # EuroLeague
LBA_SERIES_ICON = {1: ICON_SERIE_A, 5: ICON_COPPA, 6: ICON_COPPA}

EL_BASE = "https://feeds.incrowdsports.com/provider/euroleague-feeds/v2"
EL_COMPETITION = "E"
EL_TEAM_CODE = "VIR"

GAME_DURATION = timedelta(hours=2)
USER_AGENT = (
    "Mozilla/5.0 (compatible; virtus-calendar/1.0; "
    "+https://github.com/) Python-urllib"
)
REQUEST_PAUSE = 0.3  # secondi tra una richiesta e l'altra, per gentilezza


# --------------------------------------------------------------------------- #
# Modello dati
# --------------------------------------------------------------------------- #

@dataclass
class Game:
    uid: str
    competition: str              # "LBA" o "EuroLeague"
    start: datetime | None        # timezone-aware; None se orario da definire
    day: date                     # giorno della partita (usato se start è None)
    home: str
    away: str
    stage: str                    # es. "3° Giornata", "Round 12", "Semifinali - Gara 1"
    venue: str = ""
    city: str = ""
    score: tuple[int, int] | None = None   # (casa, trasferta) se giocata; non mostrato nel titolo
    opponent: str = ""                      # codice avversario, per trovare lo scontro precedente
    series_key: str | None = None           # gruppo in cui cercare i precedenti; None = niente
    series_mode: str | None = None          # "rs" = andata/ritorno, "playoff" = gare della serie
    previous: str | None = None             # testo dei precedenti da mettere in descrizione
    icon: str = ""
    virtus_home: bool = True
    opponent_name: str = ""
    stamp: str = "20260101T000000Z"

    @property
    def time_tbd(self) -> bool:
        return self.start is None


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

def fetch_json(url: str, retries: int = 3) -> dict:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            time.sleep(REQUEST_PAUSE)
            return data
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Impossibile scaricare {url}: {last_err}")


# --------------------------------------------------------------------------- #
# LBA
# --------------------------------------------------------------------------- #

def _is_virtus_lba(code: str | None, name: str | None) -> bool:
    return code == LBA_CLUB_CODE and LBA_NAME_HINT in (name or "").lower()


def _virtus_name(name: str, is_virtus: bool) -> str:
    return "Virtus Bologna" if is_virtus else name


def parse_lba_matches(
    payload: dict,
    competition_name: str,
    series_key: str | None = None,
    series_mode: str | None = None,
    icon: str = ICON_SERIE_A,
) -> list[Game]:
    """Estrae le partite della Virtus da una risposta di get-championships-calendar-by-id."""
    games: list[Game] = []
    for m in payload.get("matches") or []:
        h_virtus = _is_virtus_lba(m.get("h_club_code"), m.get("h_team_name"))
        v_virtus = _is_virtus_lba(m.get("v_club_code"), m.get("v_team_name"))
        if not (h_virtus or v_virtus):
            continue

        dt = datetime.fromisoformat(m["match_datetime"])
        tbd = (m.get("match_hh") or 0) == 0 and (m.get("match_mm") or 0) == 0

        score = None
        hs, vs = m.get("home_final_score") or 0, m.get("visitor_final_score") or 0
        if (hs or vs) and dt < datetime.now(timezone.utc):
            score = (hs, vs)

        stage = m.get("day_name") or ""
        if competition_name and "regular season" not in competition_name.lower():
            stage = f"{competition_name} · {stage}" if stage else competition_name

        stamp = _stamp_from_iso(m.get("updated_at"))
        games.append(
            Game(
                uid=f"lba-{m['id']}@virtus-calendar",
                competition="LBA",
                start=None if tbd else dt,
                day=dt.date(),
                home=_virtus_name(m.get("h_team_name", ""), h_virtus),
                away=_virtus_name(m.get("v_team_name", ""), v_virtus),
                stage=stage.strip(),
                venue=m.get("plant_name") or "",
                city=m.get("town_name") or "",
                score=score,
                opponent=(m.get("v_club_code") if h_virtus else m.get("h_club_code")) or "",
                series_key=series_key,
                series_mode=series_mode,
                icon=icon,
                virtus_home=h_virtus,
                opponent_name=(m.get("v_team_name") if h_virtus else m.get("h_team_name")) or "",
                stamp=stamp,
            )
        )
    return games


def fetch_lba_games() -> list[Game]:
    comps = fetch_json(f"{LBA_BASE}/championships/get-championships?current=1&items=1000")
    games: dict[str, Game] = {}
    for comp in comps.get("competitions") or []:
        if comp.get("championship_series_id") not in LBA_SERIES:
            continue
        cid = comp["id"]
        name = comp.get("name") or ""
        # Regular season -> andata; playoff -> gare precedenti della serie;
        # coppe (Coppa Italia, Supercoppa) -> niente.
        ctype = comp.get("ctype_code")
        mode = {"RS": "rs", "PO": "playoff"}.get(ctype)
        series_key = f"LBA-{cid}" if mode else None
        base_url = f"{LBA_BASE}/championships/get-championships-calendar-by-id?id={cid}"
        first = fetch_json(base_url)
        days = (first.get("filters") or {}).get("days") or []
        if not days:
            payloads = [first]
        else:
            payloads = [fetch_json(f"{base_url}&d={d['event_serial']}") for d in days]
        for p in payloads:
            icon = LBA_SERIES_ICON.get(comp.get("championship_series_id"), ICON_SERIE_A)
            for g in parse_lba_matches(p, name, series_key, mode, icon):
                games[g.uid] = g
    return list(games.values())


# --------------------------------------------------------------------------- #
# EuroLeague
# --------------------------------------------------------------------------- #

def current_el_season(today: date | None = None) -> str:
    today = today or date.today()
    year = today.year if today.month >= 7 else today.year - 1
    return f"{EL_COMPETITION}{year}"


def parse_el_games(payload: dict) -> list[Game]:
    games: list[Game] = []
    for g in payload.get("data") or []:
        home, away = g.get("home") or {}, g.get("away") or {}
        h_virtus = home.get("code") == EL_TEAM_CODE
        a_virtus = away.get("code") == EL_TEAM_CODE
        if not (h_virtus or a_virtus):
            continue

        dt = datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
        tbd = not (g.get("confirmedDate", True) and g.get("confirmedTime", True))

        score = None
        if g.get("status") == "result":
            score = (home.get("score") or 0, away.get("score") or 0)

        phase = (g.get("phaseType") or {}).get("name") or ""
        rnd = (g.get("round") or {}).get("name") or ""
        stage = rnd if phase.lower() == "regular season" else " · ".join(x for x in (phase, rnd) if x)

        venue = g.get("venue") or {}
        # RS -> andata; PO -> gare precedenti della serie; play-in e Final Four -> niente.
        mode = {"RS": "rs", "PO": "playoff"}.get((g.get("phaseType") or {}).get("code"))
        season = (g.get("season") or {}).get("code") or g["identifier"].split("_")[0]

        games.append(
            Game(
                uid=f"euroleague-{g['identifier']}@virtus-calendar",
                competition="EuroLeague",
                start=None if tbd else dt,
                day=dt.astimezone(_rome()).date(),
                home=_virtus_name(home.get("name", ""), h_virtus),
                away=_virtus_name(away.get("name", ""), a_virtus),
                stage=stage,
                venue=(venue.get("name") or "").title(),
                city=venue.get("address") or "",
                score=score,
                opponent=(away.get("code") if h_virtus else home.get("code")) or "",
                series_key=f"EL-{season}-{mode}" if mode else None,
                series_mode=mode,
                icon=ICON_EL,
                virtus_home=h_virtus,
                opponent_name=(away.get("name") if h_virtus else home.get("name")) or "",
            )
        )
    return games


def fetch_el_games(season: str | None = None) -> list[Game]:
    season = season or current_el_season()
    games: dict[str, Game] = {}
    limit, offset = 100, 0
    while True:
        q = urllib.parse.urlencode({"teamCode": EL_TEAM_CODE, "limit": limit, "offset": offset})
        url = f"{EL_BASE}/competitions/{EL_COMPETITION}/seasons/{season}/games?{q}"
        payload = fetch_json(url)
        items = payload.get("data") or []
        for g in parse_el_games(payload):
            games[g.uid] = g
        total = (payload.get("metadata") or {}).get("totalItems") or 0
        offset += len(items)
        if not items or offset >= total:
            break
    return list(games.values())


# --------------------------------------------------------------------------- #
# Scontro precedente (andata) nella stessa competizione
# --------------------------------------------------------------------------- #

def _sort_key(g: Game):
    return (g.day, g.start or datetime.min.replace(tzinfo=timezone.utc))


def _result(g: Game) -> str:
    return f"{g.home} {g.score[0]} – {g.score[1]} {g.away}"


def add_previous_meetings(games: list[Game]) -> None:
    """Aggiunge in descrizione i precedenti contro lo stesso avversario:
      - regular season: il risultato dell'andata (stessa competizione e stagione);
      - playoff: tutte le gare già giocate della serie (da gara 2 in poi);
      - competizioni senza series_key (coppe, play-in, Final Four): nulla."""
    groups: dict[tuple[str, str], list[Game]] = {}
    for g in games:
        if g.series_key and g.opponent:
            groups.setdefault((g.series_key, g.opponent), []).append(g)
    for group in groups.values():
        group.sort(key=_sort_key)
        for i, g in enumerate(group):
            earlier = group[:i]
            if g.series_mode == "rs":
                played = [p for p in earlier if p.score]
                if played:
                    p = played[-1]
                    g.previous = f"Andata ({p.day.strftime('%d/%m/%Y')}): {_result(p)}"
            elif g.series_mode == "playoff":
                lines = [
                    f"Gara {n} ({p.day.strftime('%d/%m')}): {_result(p)}"
                    for n, p in enumerate(earlier, start=1)
                    if p.score
                ]
                if lines:
                    g.previous = "Serie playoff:\n" + "\n".join(lines)


# --------------------------------------------------------------------------- #
# iCalendar
# --------------------------------------------------------------------------- #

def _rome():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Rome")
    except Exception:  # noqa: BLE001
        return timezone(timedelta(hours=1))


def _stamp_from_iso(value: str | None) -> str:
    if not value:
        return "20260101T000000Z"
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    except ValueError:
        return "20260101T000000Z"


def _esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Spezza le righe oltre i 75 byte come richiesto da RFC 5545."""
    out, cur = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        limit = 75 if not out else 74
        if len(cur) + len(enc) > limit:
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += enc
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def game_summary(g: Game) -> str:
    # Formato: <icona> vs. <avversario>  (in casa)
    #          <icona> @ <avversario>    (in trasferta)
    sep = "vs." if g.virtus_home else "@"
    return f"{g.icon} {sep} {g.opponent_name}"


def game_description(g: Game) -> str:
    lines = [g.competition + (f" – {g.stage}" if g.stage else "")]
    if g.time_tbd:
        lines.append("Orario non ancora ufficializzato: il calendario si aggiorna da solo.")
    if g.previous:
        lines.append(g.previous)
    source = "legabasket.it" if g.competition == "LBA" else "euroleaguebasketball.net"
    lines.append(f"Fonte: {source}")
    return "\n".join(lines)


def build_ics(games: list[Game], name: str, description: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//virtus-calendar//IT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(name)}",
        f"X-WR-CALDESC:{_esc(description)}",
        "X-WR-TIMEZONE:Europe/Rome",
        "REFRESH-INTERVAL;VALUE=DURATION:PT24H",
        "X-PUBLISHED-TTL:PT24H",
    ]
    for g in sorted(games, key=_sort_key):
        lines += ["BEGIN:VEVENT", f"UID:{g.uid}", f"DTSTAMP:{g.stamp}"]
        if g.start is None:
            lines.append(f"DTSTART;VALUE=DATE:{g.day.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{(g.day + timedelta(days=1)).strftime('%Y%m%d')}")
            lines.append("TRANSP:TRANSPARENT")
        else:
            lines.append(f"DTSTART:{_utc(g.start)}")
            lines.append(f"DTEND:{_utc(g.start + GAME_DURATION)}")
        lines.append(f"SUMMARY:{_esc(game_summary(g))}")
        location = ", ".join(x for x in (g.venue, g.city) if x)
        if location:
            lines.append(f"LOCATION:{_esc(location)}")
        lines.append(f"DESCRIPTION:{_esc(game_description(g))}")
        lines.append(f"CATEGORIES:{g.competition}")
        lines.append("STATUS:CONFIRMED" if not g.time_tbd else "STATUS:TENTATIVE")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8", newline="")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera il calendario .ics della Virtus Bologna")
    ap.add_argument("--out", default="docs", help="cartella di destinazione (default: docs)")
    ap.add_argument("--el-season", default=None, help="codice stagione EuroLeague, es. E2026")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Se una delle due fonti fallisce, usciamo con errore SENZA toccare i file
    # esistenti: meglio un calendario vecchio di qualche ora che uno vuoto.
    try:
        lba = fetch_lba_games()
        el = fetch_el_games(args.el_season)
    except Exception as e:  # noqa: BLE001
        print(f"ERRORE: {e}", file=sys.stderr)
        return 1

    if not lba and not el:
        print("ERRORE: nessuna partita trovata, non aggiorno i file.", file=sys.stderr)
        return 1

    add_previous_meetings(lba + el)

    outputs = {
        "virtus.ics": (lba + el, "Virtus Bologna 🏀", "Partite Virtus Bologna: LBA ed EuroLeague"),
        "virtus-lba.ics": (lba, "Virtus Bologna · LBA", "Partite Virtus Bologna in LBA"),
        "virtus-euroleague.ics": (el, "Virtus Bologna · EuroLeague", "Partite Virtus Bologna in EuroLeague"),
    }
    for filename, (games, name, desc) in outputs.items():
        changed = write_if_changed(out / filename, build_ics(games, name, desc))
        print(f"{filename}: {len(games)} partite{' (aggiornato)' if changed else ''}")

    tbd = sum(1 for g in lba + el if g.time_tbd)
    print(f"LBA: {len(lba)} · EuroLeague: {len(el)} · orari da definire: {tbd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
