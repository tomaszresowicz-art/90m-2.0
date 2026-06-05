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
    
    # 1. Maskowanie: Nagłówki identyczne z prawdziwą przeglądarką Chrome
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive"
    }
    
    # 2. KLUCZOWE: Wstrzykiwanie ciasteczek akceptacji RODO i sesji, by serwer wyrenderował tabele
    cookies = {
        "90minut_cmp_consent": "true",
        "90minut_rodo_accepted": "1",
        "@@scroll_top": "0"
    }
    session.cookies.update(cookies)
    
    dzis = datetime.now()
    total_steps = len(identyfikatory_okregow) * (liczba_dni + 1)
    
    if total_steps == 0:
        return pd.DataFrame(), "Nie wybrano żadnego okręgu."

    progress_bar = st.progress(0)
    status_text = st.empty()
    step = 0
    ostatnia_surowa_odpowiedz = "Rozpoczęto pętlę pobierania."

    for id_okreg in identyfikatory_okregow:
        nazwa_okregu = OKREGI[id_okreg]

        for i in range(liczba_dni + 1):
            celowana_data = dzis + timedelta(days=i)
            data_str = celowana_data.strftime("%Y-%m-%d")

            step += 1
            procent = int((step / total_steps) * 100)
            progress_bar.progress(procent)
            status_text.text(f"Pobieranie danych: {nazwa_okregu} ➡️ {data_str}")

            # Budujemy pełny URL ręcznie, żeby wykluczyć błędy kodowania parametrów
            full_url = f"http://www.90minut.pl/mecze_okreg.php?id_okreg={id_okreg}&data={data_str}"

            dzien_tygodnia = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"][celowana_data.weekday()]
            miesiace_pl = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
            formatowana_data_pl = f"{celowana_data.day} {miesiace_pl[celowana_data.month]} {celowana_data.year} ({dzien_tygodnia})"

            try:
                response = session.get(full_url, headers=headers, timeout=12)
                ostatnia_surowa_odpowiedz = f"Status HTTP: {response.status_code}\nURL: {full_url}\n\n"
                
                if response.status_code == 200:
                    response.encoding = 'iso-8859-2'
                    html_text = response.text
                    ostatnia_surowa_odpowiedz += html_text
                    
                    soup = BeautifulSoup(html_text, "html.parser")
                    
                    # Szukamy wierszy tabeli (tr)
                    wiersze = soup.find_all("tr")
                    current_league = "Rozgrywki"
                    
                    for row in wiersze:
                        # Sprawdzamy czy wiersz definiuje ligę
                        league_cell = row.find(["th", "td"], {"class": "vader"}) or row.find("b")
                        if league_cell and not row.find("a"):
                            text_l = league_cell.get_text(strip=True)
                            if text_l and not text_l.isdigit() and ":" not in text_l and "Wybierz" not in text_l:
                                current_league = text_l
                                continue
                        
                        # Sprawdzamy czy to wiersz z meczem
                        cols = row.find_all("td")
                        if len(cols) >= 2:
                            time_text = cols[0].get_text(strip=True)
                            
                            # Czy pierwsza kolumna to format godziny HH:MM
                            if ":" in time_text and len(time_text) <= 5 and time_text[0].isdigit():
                                teams_text = cols[1].get_text(strip=True)
                                score_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                                
                                if teams_text and "wypisz_zapowiedzi" not in teams_text:
                                    all_matches.append({
                                        "Data_Sort": celowana_data.date(),
                                        "Dzień": formatowana_data_pl,
                                        "Okręg / Związek": nazwa_okregu,
                                        "Rozgrywki / Liga": current_league,
                                        "Godzina": time_text,
                                        "Mecz": teams_text,
                                        "Wynik": score_text
                                    })
                
                time.sleep(0.1) # Naturalna mikropauza
                
            except Exception as e:
                ostatnia_surowa_odpowiedz = f"Wyjątek połączenia: {str(e)}"

    progress_bar.empty()
    status_text.empty()

    df = pd.DataFrame(all_matches)
    if not df.empty:
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Data_Sort", "Sort_Time", "Rozgrywki / Liga"])
        
    return df, ostatnia_surowa_odpowiedz

# 3. Prezentacja danych w UI
if not wybrane_id:
    st.info("👈 Wybierz przynajmniej jeden okręg na panelu bocznym i kliknij 'Znajdź mecze'.")
else:
    if "pobrane_dane" not in st.session_state:
        st.session_state.pobrane_dane = None
    if "debug_html" not in st.session_state:
        st.session_state.debug_html = "Brak danych diagnostycznych."

    if shortcuts := uruchom_szukanie:
        with st.spinner("Pobieranie terminarza przy użyciu pancernej sesji RODO..."):
            df, debug = pobierz_mecze_precyzyjnie(wybrane_id, LICZBA_DNI_W_PRZOD)
            st.session_state.pobrane_dane = df
            st.session_state.debug_html = debug

    if st.session_state.pobrane_dane is not None:
        df_mecze = st.session_state.pobrane_dane

        if df_mecze.empty:
            st.error("❌ Parser nie odnalazł meczów w kodzie strony pomimo połączenia z serwerem.")
            with st.expander("🛠️ Kod źródłowy zwrócony przez serwer (Zweryfikuj teraz)", expanded=True):
                st.code(st.session_state.debug_html[:4000])
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
                
                with st.expander(naglowek_sekcji, expanded=False):
                    if df_okregu.empty:
                        st.info("Brak meczów spełniających kryteria wyszukiwania.")
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
