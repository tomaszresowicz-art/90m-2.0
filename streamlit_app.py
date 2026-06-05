import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import re

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

# 2. Ustawienia Streamlit
st.set_page_config(page_title="Terminarz 90minut", layout="wide", page_icon="⚽")

st.title("⚽ Interaktywny Terminarz 90minut.pl")
st.caption("Skonfiguruj filtry w panelu bocznym i kliknij przycisk '🔍 Znajdź mecze'.")

# Panel boczny (Sidebar)
with st.sidebar:
    st.header("⚙️ Ustawienia wyszukiwania")
    
    wybrane_nazwy = st.multiselect(
        "Wybierz okręgi/związki:",
        options=list(OKREGI.values()),
        default=["Szczebel Centralny / Krajowy", "Małopolski ZPN"]
    )

    LICZBA_DNI_W_PRZOD = st.slider("Zakres wyszukiwania (w dniach):", min_value=1, max_value=14, value=14)
    
    st.write("---")
    uruchom_szukanie = st.button("🔍 Znajdź mecze", type="primary", use_container_width=True)
    
    if st.button("🔄 Wyczyść pamięć (Cache)", use_container_width=True):
        st.cache_data.clear()
        if "pobrane_dane" in st.session_state:
            del st.session_state.pobrane_dane
        if "debug_html" in st.session_state:
            del st.session_state.debug_html
        st.rerun()

wybrane_id = [k for k, v in OKREGI.items() if v in wybrane_nazwy]

@st.cache_data(ttl=600)
def pobierz_mecze_precyzyjnie(identyfikatory_okregow, liczba_dni):
    all_matches = []
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive"
    }
    
    cookies = {
        "90minut_cmp_consent": "true",
        "90minut_rodo_accepted": "1"
    }
    session.cookies.update(cookies)
    
    base_url = "http://www.90minut.pl/mecze_okreg.php"
    dzis = datetime.now()
    total_steps = len(identyfikatory_okregow) * (liczba_dni + 1)
    
    if total_steps == 0:
        return pd.DataFrame(), "Nie wybrano żadnego okręgu."

    progress_bar = st.progress(0)
    status_text = st.empty()
    step = 0
    ostatnia_surowa_odpowiedz = "Brak pobranych danych (wszystkie dni mogły być puste)."

    regex_godzina = re.compile(r'^\d{1,2}:\d{2}$')

    for id_okreg in identyfikatory_okregow:
        nazwa_okregu = OKREGI[id_okreg]

        for i in range(liczba_dni + 1):
            celowana_data = dzis + timedelta(days=i)
            data_str = celowana_data.strftime("%Y-%m-%d")

            step += 1
            procent = int((step / total_steps) * 100)
            progress_bar.progress(procent)
            status_text.text(f"Analiza terminarza: {nazwa_okregu} ➡️ {data_str}")

            payload = {
                "id_okreg": str(id_okreg),
                "data": data_str
            }

            dni_tygodnia_pl = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
            dzien_tygodnia = dni_tygodnia_pl[celowana_data.weekday()]
            
            miesiace_pl = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
            formatowana_data_pl = f"{celowana_data.day} {miesiace_pl[celowana_data.month]} {celowana_data.year} ({dzien_tygodnia})"

            try:
                response = session.get(base_url, params=payload, headers=headers, timeout=12)
                
                if response.status_code == 200:
                    response.encoding = 'iso-8859-2'
                    html_text = response.text
                    
                    soup = BeautifulSoup(html_text, "html.parser")
                    main_headers = [b.get_text(strip=True) for b in soup.find_all("b")[:6]]
                    
                    # DETEKCJA STRONY GŁÓWNEJ: Jeśli na stronie są nagłówki Skarbu lub Transferów, 
                    # oznacza to, że w tym dniu nie ma meczów i serwer przekierował nas na główną. Pomijamy!
                    if 'Skarb Ekstraklasy' in main_headers or 'Transfery - Ekstr.' in main_headers:
                        continue
                    
                    # Jeśli to prawdziwa podstrona terminarza, zapisujemy ją jako ostatni punkt diagnostyczny
                    ostatnia_surowa_odpowiedz = f"Ostatni udany URL z meczami: {response.url}\nNagłówki <b>: {main_headers}\n\n--- KOD ---\n{html_text[:1000]}"
                    
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
                                    all_matches.append({
                                        "Data_Sort": celowana_data.date(),
                                        "Dzień": formatowana_data_pl,
                                        "Okręg / Związek": nazwa_okregu,
                                        "Rozgrywki / Liga": current_league,
                                        "Godzina": time_text,
                                        "Mecz": teams_text,
                                        "Wynik": score_text
