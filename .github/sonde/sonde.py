"""Sonde temporaire : HTML condensé des grilles RTL, Europe 1 et Sud Radio (pour écrire les lecteurs)."""
import re

import requests

EN_TETES = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15", "Accept-Language": "fr-FR,fr;q=0.9"}


def condenser(h):
    h = re.sub(r"(?is)<(svg|picture|script|style|noscript)[^>]*>.*?</\1>", "", h)
    h = re.sub(r"(?is)<(img|source|meta|link|input)[^>]*>", "", h)
    h = re.sub(r"(?is)<button[^>]*>.*?</button>", "", h)
    h = re.sub(r'\s(data-(?!jour|day|role)[\w-]+|style|aria-[\w-]+|itemprop|itemscope|itemtype|loading|width|height)="[^"]*"', "", h)
    h = re.sub(r"\n\s*\n+", "\n", h)
    return re.sub(r"[ \t]+", " ", h)


def get(url):
    r = requests.get(url, headers=EN_TETES, timeout=30)
    r.encoding = "utf-8"
    print("=" * 90)
    print(url, r.status_code, r.url, len(r.text))
    return r.text


# RTL : la carte qui contient RTL Matin, en entier, puis la liste des titres de cartes et chroniques.
h = get("https://www.rtl.fr/grille/13-10-2026")
cartes = re.split(r'(?=<div class="programme-card[ "])', h)
print("cartes :", len(cartes) - 1)
for c in cartes[1:]:
    if "RTL Matin" in c or "RTL Midi" in c:
        print(condenser(c)[:9000])
        break
print("--- toutes les cartes (heure, titre) ---")
for c in cartes[1:]:
    t = re.search(r'programme-card__time[^>]*>(.*?)<', c)
    ti = re.search(r'programme-card__title[^>]*>(.*?)<', c)
    print(" ", t.group(1).strip() if t else "?", "|", ti.group(1).strip() if ti else "?")

# Europe 1 : repères des jours, puis le début du lundi condensé.
h = get("https://www.europe1.fr/grille-des-programmes")
for m in re.finditer(r'<[^>]+(?:id|data-day|data-jour|data-tab)="[^"]*(?:lundi|mardi|monday|tuesday|jour|day)[^"]*"[^>]*>', h, re.I):
    print("  repère jour :", m.group(0)[:200])
i = h.find("05h00 - 07h00")
print(condenser(h[max(0, i - 4000): i + 7000]))

# Sud Radio : les trois premières lignes du lundi, condensées, puis la ligne de 8 h.
h = get("https://www.sudradio.fr/programmes")
lignes = re.split(r'(?=<li class="sud_planning_ligne)', h)
print("lignes :", len(lignes) - 1)
for l in lignes[1:4]:
    print(condenser(l)[:3500])
    print("-" * 40)
for l in lignes[1:]:
    if "08H" in l[:3000] or "08h" in l[:3000]:
        print(condenser(l)[:3500])
        break
