import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import random
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
st.caption("Aplikacja korzysta z tunelowania zapytań, aby ominąć blokady hostingu Streamlit.")

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
    dzis = datetime.now()
    total_steps = len(identyfikatory_okregow) * (liczba_dni + 1)
    
    if total_steps == 0:
        return pd.DataFrame(), "Nie wybrano żadnego okręgu."

    progress_bar = st.progress(0)
    status_text = st.empty()
    step = 0
    ostatnia_surowa_odpowiedz = "Brak pobranych danych."

    regex_godzina = re.compile(r'^\d{1,2}:\d{2}$')

    for id_okreg in identyfikatory_okregow:
        nazwa_okregu = OKREGI[id_okreg]

        for i in range(liczba_dni + 1):
            celowana_data = dzis + timedelta(days=i)
            data_str = celowana_data.strftime("%Y-%m-%d")

            step += 1
            procent = int((step / total_steps) * 100)
            progress_bar.progress(procent)
            status_text.text(f"Pobieranie przez proxy: {nazwa_okregu} ➡️ {data_str}")

            # Oryginalny, prawidłowy URL docelowy
            target_url = f"http://www.90minut.pl/mecze_okreg.php?id_okreg={id_okreg}&data={data_str}"
            
            # OBEJŚCIE BLOKADY: Używamy otwieranego publicznie proxy allorigins do zamaskowania IP chmury AWS
            proxy_url = f"https://api.allorigins.win/get?url={requests.utils.quote(target_url)}"

            dni_tygodnia_pl = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
            dzien_tygodnia = dni_tygodnia_pl[celowana_data.weekday()]
            miesiace_pl = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
            formatowana_data_pl = f"{celowana_data.day} {miesiace_pl[celowana_data.month]} {celowana_data.year} ({dzien_tygodnia})"

            try:
                # Zapytanie idzie do bramki proxy, a bramka pobiera kod z 90minut i oddaje nam JSON-a
                response = requests.get(proxy_url, timeout=15)
                
                if response.status_code == 200:
                    data_json = response.json()
                    html_text = data_json.get("contents", "")
                    
                    soup = BeautifulSoup(html_text, "html.parser")
                    main_headers = [b.get_text(strip=True) for b in soup.find_all("b")[:6]]
                    
                    # Weryfikacja, czy proxy nie dostało pustego szablonu strony głównej
                    if 'Skarb Ekstraklasy' in main_headers or 'Transfery - Ekstr.' in main_headers:
                        continue
                    
                    ostatnia_surowa_odpowiedz = f"Sukces! Tunelowanie URL: {target_url}\nNagłówki <b> strony: {main_headers}"
                    
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
                                    })
                
                # Niewielki odstęp czasowy
                time.sleep(0.2)
                
            except Exception as e:
                ostatnia_surowa_odpowiedz = f"Błąd bramki proxy dla URL {target_url}: {str(e)}"

    progress_bar.empty()
    status_text.empty()

    df = pd.DataFrame(all_matches)
    if not df.empty:
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Data_Sort", "Sort_Time", "Rozgrywki / Liga"])
        
    return df, ostatnia_surowa_odpowiedz

# 3. Wyświetlanie wyników w UI
if not wybrane_id:
    st.info("👈 Wybierz okręgi w panelu bocznym i kliknij 'Znajdź mecze'.")
else:
    if "pobrane_dane" not in st.session_state:
        st.session_state.pobrane_dane = None
    if "debug_html" not in st.session_state:
        st.session_state.debug_html = "Brak danych."

    if uruchom_szukanie:
        with st.spinner("Pobieranie terminarza przez niezależne proxy sieciowe..."):
            df, debug = pobierz_mecze_precyzyjnie(wybrane_id, LICZBA_DNI_W_PRZOD)
            st.session_state.pobrane_dane = df
            st.session_state.debug_html = debug

    if st.session_state.pobrane_dane is not None:
        df_mecze = st.session_state.pobrane_dane

        if df_mecze.empty:
            st.error("❌ Serwer proxy nie zdołał ominąć zabezpieczeń lub brak meczów w wybranym przedziale.")
            with st.expander("🛠️ Szczegóły ostatniego żądania", expanded=True):
                st.code(st.session_state.debug_html)
        else:
            search_query = st.text_input("🔍 Szybki filtr tabeli (wpisz klub lub ligę):", "")
            df_filtrowane = df_mecze.copy()
            
            if search_query:
                df_filtrowane = df_filtrowane[df_filtrowane.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

            st.write("---")
            
            for id_okreg in wybrane_id:
                nazwa_okregu = OKREGI[id_okreg]
                df_okregu = df_filtrowane[df_filtrowane["Okręg / Związek"] == nazwa_okregu]
                
                liczba_meczów = len(df_okregu)
                naglowek_sekcji = f"📍 {nazwa_okregu} (Zaplanowanych meczów: {liczba_meczów})"
                
                with st.expander(naglowek_sekcji, expanded=True if liczba_meczów > 0 else False):
                    if df_okregu.empty:
                        st.info("Brak meczów spełniających kryteria dla tego regionu.")
                    else:
                        df_wyswietl = df_okregu.drop(columns=["Okręg / Związek", "Data_Sort", "Sort_Time"], errors='ignore')
                        st.dataframe(
                            df_wyswietl,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Dzień": st.column_config.TextColumn("📅 Data i dzień", width="medium"),
                                "Rozgrywki / Liga": st.column_config.TextColumn("🏆 Rozgrywki", width="medium"),
                                "Godzina": st.column_config.TextColumn("⏰ Godzina", width="small"),
                                "Mecz": st.column_config.TextColumn("⚔️ Spotkanie", width="large"),
                                "Wynik": st.column_config.TextColumn("📊 Wynik", width="small"),
                            }
                        )
    else:
        st.info("👈 Skonfiguruj filtry po lewej stronie i kliknij '🔍 Znajdź mecze'.")
