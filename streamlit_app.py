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
st.caption("Skonfiguruj filtry poniżej i kliknij przycisk '🔍 Znajdź mecze', aby pobrać aktualne zapowiedzi.")

# Formularz blokujący automatyczne odświeżanie przy każdym kliknięciu
with st.sidebar:
    st.header("⚙️ Ustawienia wyszukiwania")
    
    # Wielokrotny wybór okręgów w UI
    wybrane_nazwy = st.multiselect(
        "Wybierz okręgi/związki:",
        options=list(OKREGI.values()),
        default=["Szczebel Centralny / Krajowy", "Małopolski ZPN"]
    )

    # Suwak do wyboru zakresu dni (domyślnie 14 dni)
    LICZBA_DNI_W_PRZOD = st.slider("Zakres wyszukiwania (w dniach):", min_value=1, max_value=14, value=14)
    
    st.write("---")
    # GŁÓWNY PRZYCISK URUCHAMIAJĄCY
    uruchom_szukanie = st.button("🔍 Znajdź mecze", type="primary", use_container_width=True)
    
    # Przycisk awaryjny czyszczący cache
    if st.button("🔄 Wyczyść pamięć (Cache)", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Pobieramy ID dla wybranych nazw okręgów
wybrane_id = [k for k, v in OKREGI.items() if v in wybrane_nazwy]

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
            status_text.text(f"Pobieranie danych: {nazwa_okregu} ➡️ {data_str}")

            parametry = {
                "id_okreg": str(id_okreg),
                "data": data_str
            }

            dzien_tygodnia = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"][celowana_data.weekday()]
            miesiace_pl = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
            formatowana_data_pl = f"{celowana_data.day} {miesiace_pl[celowana_data.month]} {celowana_data.year} ({dzien_tygodnia})"

            try:
                response = requests.get(base_url, params=parametry, headers=headers, timeout=10)
                if response.status_code == 200:
                    response.encoding = 'iso-8859-2'
                    soup = BeautifulSoup(response.text, "html.parser")
                    main_table = soup.find("table", {"class": "main"})
                    
                    if main_table:
                        current_league = "Inne rozgrywki"

                        for row in main_table.find_all("tr"):
                            # Detekcja nazwy rozgrywek / ligi
                            date_tag = row.find("th") or row.find("td", {"class": "vader"})
                            if date_tag and "href" not in str(date_tag):
                                text = date_tag.get_text(strip=True)
                                if text and not text.isdigit() and "Wybierz" not in text and ":" not in text:
                                    current_league = text
                                continue

                            league_tag = row.find("b")
                            if league_tag and not row.find("a") and not league_tag.get_text(strip=True).isdigit():
                                text_league = league_tag.get_text(strip=True)
                                if ":" not in text_league and "Wybierz" not in text_league:
                                    current_league = text_league
                                continue

                            # Wyciąganie meczu
                            cols = row.find_all("td")
                            if len(cols) >= 2:
                                time_text = cols[0].get_text(strip=True)
                                
                                # Walidacja formatu godziny (HH:MM)
                                if ":" in time_text and len(time_text) <= 5:
                                    teams_text = cols[1].get_text(strip=True)
                                    score_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                                    
                                    all_matches.append({
                                        "Data_Sort": celowana_data.date(),
                                        "Dzień": formatowana_data_pl,
                                        "Okręg / Związek": nazwa_okregu,
                                        "Rozgrywki / Liga": current_league,
                                        "Godzina": time_text,
                                        "Mecz": teams_text,
                                        "Wynik": score_text
                                    })
                time.sleep(0.05)
            except Exception:
                pass

    progress_bar.empty()
    status_text.empty()

    df = pd.DataFrame(all_matches)
    
    if not df.empty:
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Data_Sort", "Sort_Time", "Rozgrywki / Liga"])
        
    return df

# 3. Logika wyświetlania wyników
if not wybrane_id:
    st.info("👈 Wybierz przynajmniej jeden okręg na panelu bocznym i kliknij 'Znajdź mecze'.")
else:
    # Program rusza tylko, jeśli użytkownik wcisnął przycisk LUB dane są już w sesji
    if uruchom_szukanie or "pobrane_dane" in st.session_state:
        
        try:
            # Zapisujemy wynik do stanu sesji, żeby wyszukiwarka tekstowa nie resetowała pobranych danych
            if uruchom_szukanie or "pobrane_dane" not in st.session_state:
                with st.spinner("Łączenie z bazą danych 90minut.pl..."):
                    st.session_state.pobrane_dane = pobierz_mecze_precyzyjnie(wybrane_id, LICZBA_DNI_W_PRZOD)

            df_mecze = st.session_state.pobrane_dane

            if df_mecze.empty:
                st.warning("Brak zaplanowanych meczów w wybranym okresie dla tych okręgów. Spróbuj wyczyścić cache boczny.")
            else:
                # Globalna wyszukiwarka tekstowa
                search_query = st.text_input("🔍 Filtruj wyniki wewnątrz list (wpisz klub lub ligę):", "")
                
                df_filtrowane = df_mecze.copy()
                if search_query:
                    df_filtrowane = df_filtrowane[df_filtrowane.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

                st.write("---")
                
                # Budowanie rozwijanych pasków (Expanders)
                for id_okreg in wybrane_id:
                    nazwa_okregu = OKREGI[id_okreg]
                    df_okregu = df_filtrowane[df_filtrowane["Okręg / Związek"] == nazwa_okregu]
                    
                    liczba_meczów = len(df_okregu)
                    naglowek_sekcji = f"📍 {nazwa_okregu} (Zaplanowanych meczów: {liczba_meczów})"
                    
                    with st.expander(naglowek_sekcji, expanded=False):
                        if df_okregu.empty:
                            st.info("Brak meczów dla tego okręgu spełniających kryteria wyszukiwania.")
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
        except Exception as e:
            st.error(f"Błąd aplikacji: {e}")
    else:
        st.info("👈 Kliknij czerwony/niebieski przycisk '🔍 Znajdź mecze' na panelu bocznym, aby rozpocząć skanowanie serwera.")
