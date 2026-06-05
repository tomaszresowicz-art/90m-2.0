import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re
import json

# 1. Słownik mapujący ID okręgów na czytelne nazwy
OKREGI = {
    0: "Szczebel Centralny / Krajowy",
    1: "Dolnośląski ZPN",
    2: "Kujawsko-Pomorski ZPN",
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

st.set_page_config(page_title="Niewykrywalny Terminarz 90minut", layout="wide", page_icon="⚽")

st.title("⚽ Niewykrywalny Terminarz 90minut.pl")
st.caption("Zapytania są wysyłane z Twojej przeglądarki (Twojego IP), całkowicie omijając blokady hostingu.")

# Panel boczny (Sidebar)
with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrane_nazwy = st.multiselect(
        "Wybierz okręgi/związki:",
        options=list(OKREGI.values()),
        default=["Małopolski ZPN"]
    )
    LICZBA_DNI_W_PRZOD = st.slider("Zakres wyszukiwania (w dniach):", min_value=1, max_value=7, value=3)
    
    st.write("---")
    uruchom = st.button("🚀 Uruchom pobieranie", type="primary", use_container_width=True)
    
    if st.button("🔄 Resetuj aplikację", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

wybrane_id = [k for k, v in OKREGI.items() if v in wybrane_nazwy]

# Funkcja parsująca surowy kod HTML
def parsuj_html_90minut(html_text, nazwa_okregu, formatowana_data_pl, celowana_data):
    matches = []
    regex_godzina = re.compile(r'^\d{1,2}:\d{2}$')
    
    soup = BeautifulSoup(html_text, "html.parser")
    main_headers = [b.get_text(strip=True) for b in soup.find_all("b")[:6]]
    
    # Ignorujemy zwrotki będące stroną główną
    if 'Skarb Ekstraklasy' in main_headers or 'Transfery - Ekstr.' in main_headers:
        return matches

    wiersze = soup.find_all("tr")
    current_league = "Rozgrywki"
    
    for row in wiersze:
        vader_cell = row.find(["th", "td"], {"class": "vader"}) or row.find("b")
        if vader_cell and not row.find("a"):
            text_l = vader_cell.get_text(strip=True)
            if text_l and not text_l.isdigit() and ":" not in text_l and len(text_l) > 3 and "Wybierz" not in text_l:
                current_league = text_l
                continue
        
        cols = row.find_all("td")
        if len(cols) >= 2:
            time_text = cols[0].get_text(strip=True)
            
            if regex_godzina.match(time_text):
                teams_text = cols[1].get_text(strip=True)
                score_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                
                if teams_text and "wypisz_zapowiedzi" not in teams_text and "poprzednie" not in teams_text:
                    matches.append({
                        "Data_Sort": celowana_data.date(),
                        "Dzień": formatowana_data_pl,
                        "Okręg / Związek": nazwa_okregu,
                        "Rozgrywki / Liga": current_league,
                        "Godzina": time_text,
                        "Mecz": teams_text,
                        "Wynik": score_text
                    })
    return matches

# Przygotowanie listy URL
list_of_urls = []
dzis = datetime.now()

for id_okreg in wybrane_id:
    for i in range(LICZBA_DNI_W_PRZOD + 1):
        c_data = dzis + timedelta(
