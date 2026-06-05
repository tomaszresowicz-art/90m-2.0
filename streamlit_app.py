import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time

# 1. Słownik mapujący ID okręgów na czytelne nazwy
OKREGI = {
    0: "Szczebel Centralny / Krajowy",
    1: "Dolnośląski ZPN",
    2: "Kujawsko-Promorski ZPN",
    3: "Lubelski ZPN",
    4: "Lubuski ZPN",
    5: "Małopolski ZPN",
    6: "Mazowiecki ZPN",
    7: "Opolski ZPN",
    8: "Podkarpacki ZPN",
    9: "Podlaski ZPN",
    10: "Pomorski ZPN",
    11: "Śląski ZPN",
    12: "Świętokrzyski ZPN",
    13: "Warmińsko-Mazurski ZPN",
    14: "Wielkopolski ZPN",
    15: "Zachodniopomorski ZPN",
    16: "Łódzki ZPN"
}

# 2. Ustawienia Streamlit
st.set_page_config(page_title="Terminarz Rozwijany - 90minut", layout="wide", page_icon="⚽")

st.title("⚽ Interaktywny Terminarz 90minut.pl")
st.caption("Wybierz interesujące Cię okręgi. Mecze wyświetlą się w wygodnych, rozwijanych listach.")

# Wielokrotny wybór okręgów w UI
wybrane_nazwy = st.multiselect(
    "Wybierz okręgi/związki do przeszukania:",
    options=list(OKREGI.values()),
    default=["Szczebel Centralny / Krajowy", "Małopolski ZPN"]
)

# Pobieramy ID dla wybranych nazw okręgów
wybrane_id = [k for k, v in OKREGI.items() if v in wybrane_nazwy]

# Suwak do wyboru zakresu dni (domyślnie 14 dni)
LICZBA_DNI_W_PRZOD = st.slider("Zakres wyszukiwania (w dniach):", min_value=1, max_value=14, value=14)

@st.cache_data(ttl=600)  # Pamięć podręczna na 10 minut
def pobierz_mecze_precyzyjnie(identyfikatory_okregow, liczba_dni):
    all_matches = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    base_url = "http://www.90minut.pl/mecze_okreg.php"
    dzis = datetime.now()

    total_steps = len(identyfikatory_okregow) * (liczba_dni + 1)
    if total_steps == 0:
        return pd.DataFrame()

    progress_bar = st.progress(0)
    status_text = st.empty()
    step = 0

    # Pobieranie danych
    for id_okreg in identyfikatory_okregow:
        nazwa_okregu = OKREGI[id_okreg]

        for i in range(liczba_dni + 1):
            celowana_data = dzis + timedelta(days=i)
            data_str = celowana_data.strftime("%Y-%m-%d")

            step += 1
            procent = int((step / total_steps) * 100)
            progress_bar.progress(procent)
            status_text.text(f"Pobieranie: {nazwa_okregu} ➡️ {data_str}")

            parametry = {
                "id_okreg": str(id_okreg),
                "data": data_str
            }

            dzien_tygodnia = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"][celowana_data.weekday()]
            miesiace_pl = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
