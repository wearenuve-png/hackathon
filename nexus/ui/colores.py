"""Colores por empresa para los graficos de la interfaz (solo presentacion, no toca cifras).

Una familia de color por pais y un tono distinto para cada empresa del mismo pais. Las dos paletas se
revisaron para que se distingan entre si (tambien con daltonismo, junto al nombre de cada barra) sobre el
fondo de su modo: "dark" (carbon) y "light" (papel).
"""
import unicodedata
from collections import defaultdict

COUNTRY_COLORS = {
    "dark": {"mexico": ["#22A35C", "#B5E06A"], "el salvador": ["#3D8BFF", "#9CC3FF"],
             "guatemala": ["#C04FE0", "#EDB0F5"], "panama": ["#F0A43A", "#F7CF8A"]},
    "light": {"mexico": ["#13733F", "#5FA830"], "el salvador": ["#1E66D6", "#6FA0EC"],
              "guatemala": ["#8E24AA", "#D07FE3"], "panama": ["#C0650E", "#E09A4E"]},
}
EXTRA_COLORS = {"dark": ["#2EC4B6", "#E07AA9", "#B0A89F"], "light": ["#0F8C80", "#B83A75", "#6B645C"]}


def norm_country(name) -> str:
    t = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def company_colors(companies, mode: str) -> dict:
    """{company_id: hex}. `companies` es un dict id -> objeto con `.country` (como GroupConfig.companies)."""
    fams, extra, used, out = COUNTRY_COLORS[mode], EXTRA_COLORS[mode], defaultdict(int), {}
    n_extra = 0
    for cid, c in companies.items():
        key = norm_country(c.country)
        shades = fams.get(key, [])
        if used[key] < len(shades):
            out[cid] = shades[used[key]]
        else:
            out[cid] = extra[n_extra % len(extra)]
            n_extra += 1
        used[key] += 1
    return out
