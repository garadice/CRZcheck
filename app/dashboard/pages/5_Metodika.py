"""Metodika — Vysvetlenie oznamov a metodiky."""

import streamlit as st

from app.dashboard.components.connection import show_disclaimer
from app.flags.definitions import FLAG_CATALOG

st.set_page_config(page_title="Metodika", page_icon="📖", layout="wide")

st.title("📖 Metodika")

show_disclaimer()

st.markdown("""
Tento nástroj analyzuje **metadáta** zmlúv zverejnených v Centrálnom registri zmlúv (CRZ).
Cieľom je identifikovať zmluvy s **neúplnými alebo nezvyčajnými metadátami**.

### Dôležité upozornenie

- Oznamy **nie sú** dôkazom protiprávneho konania, korupcie ani podvodu.
- Oznamy len signalizujú, že metadáta zmluvy sa odchyľujú od očakávaného štandardu.
- Všetky oznamy môžu mať legitímne vysvetlenie.
- Tento nástroj nepoužíva žiadne metódy umelej inteligencie ani strojového učenia —
  ide o jednoduché pravidlá založené na metadátach.
""")

st.divider()

st.header("🚩 Zoznam oznamov")

for code, defn in FLAG_CATALOG.items():
    sev_color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(defn.severity_default, "⚪")
    sev_label = {"low": "nízka", "medium": "stredná", "high": "vysoká"}.get(
        defn.severity_default, "?"
    )

    with st.expander(f"{sev_color} **{defn.name}** ({code}) — závažnosť: {sev_label}"):
        st.markdown(f"**Popis:** {defn.description}")
        st.markdown(f"**Metodika:** {defn.methodology}")

st.divider()

st.header("📊 Zložená závažnosť")

st.markdown("""
Individuálne oznamy môžu byť frekventé (až 60 % zmlúv môže mať aspoň jeden oznam).
Pre zníženie šumu sa používa **zložená závažnosť**:

| Počet oznamov | Závažnosť | Vysvetlenie |
|---|---|---|
| 0 | žiadna | Zmluva bez oznamov |
| 1–2 | max. individuálna závažnosť | Zodpovedá najvyššej závažnosti jednotlivých oznamov |
| 3+ | **vysoká** | Bez ohľadu na individuálne závažnosti — indikuje kumulatívny problém |

**Predvolený filter dashboardu:** stredná+ závažnosť ALEBO 2+ oznamy.
""")

st.divider()

st.header("🔒 Ochrana súkromia")

st.markdown("""
- Profily fyzických osôb (dodávatelia bez IČO a bez právnej formy) sú v dashboardu
  **predvolene skryté**.
- Ich údaje sú viditeľné len na úrovni jednotlivých zmlúv.
- Checkbox "Zobraziť fyzické osoby" umožňuje zobraziť tieto profily.

**Heuristika detekcie fyzickej osoby:**
Dodávateľ je pravdepodobne fyzická osoba, ak:
- Nemá IČO (alebo má IČO "0")
- Jeho názov neobsahuje žiadnu z právnych foriem
  (s.r.o., a.s., v.o.s., k.s., š.p., o.z., n.o., nadácia, atď.)
""")

st.divider()

st.header("📡 Zdroj dát")

st.markdown("""
- **Zdroj:** [Centrálny register zmlúv (CRZ)](https://www.crz.gov.sk/)
- **Formát:** Denné XML exporty z `https://www.crz.gov.sk/export/YYYY-MM-DD.zip`
- **Rozsah:** Posledných 90 dní (konfigurovateľné)
- **Frekvencia aktualizácie:** Denne (automatizovaná ingestia)
- **Analýza:** Len metadáta — nepoužívame PDF, OCR ani NLP.
""")
