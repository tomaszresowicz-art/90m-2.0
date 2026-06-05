import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time

# 1. Ustawienia Streamlit
st.set_page_config(page_title="Terminarz 3 Tygodnie - 90minut", layout="wide", page_icon="⚽")

st.title("⚽ 3-Tygodniowy Terminarz 90minut.pl")
st.caption("Aplikacja automatycznie skanuje kalendarz na 21 dni do przodu, agreguje mecze i układa je chronologicznie.")

# Zakres wyszukiwania: 21 dni (3 tygodnie)
LICZBA_DNI_W_PRZOD = 21

@st.cache_data(ttl=600)  # Pamięć podręczna na 10 minut, by nie przeciążać serwera 90minut
def pobierz_mecze_3_tygodnie():
    all_matches = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    base_url = "http://www.90minut.pl/mecze_okreg.php"
    dzis = datetime.now()

    # Kontener na pasek postępu w Streamlit
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i in range(LICZBA_DNI_W_PRZOD + 1):
        celowana_data = dzis + timedelta(days=i)
        
        # Aktualizacja paska postępu w UI
        procent = int((i / (LICZBA_DNI_W_PRZOD + 1)) * 100)
        progress_bar.progress(procent)
        status_text.text(f"Skanowanie daty: {celowana_data.strftime('%d-%m-%Y')}...")

        # Parametry URL wymagane przez 90minut.pl
        parametry = {
            "dzien": celowana_data.strftime("%d"),
            "miesiac": celowana_data.strftime("%m"),
            "rok": celowana_data.strftime("%Y")
        }
        
        # Przygotowanie ładnego nazewnictwa dni po polsku
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
                    current_league = "Szczebel centralny"

                    for row in main_table.find_all("tr"):
                        # Analiza nagłówków lig / okręgów
                        date_tag = row.find("th") or row.find("td", {"class": "vader"})
                        if date_tag and "href" not in str(date_tag):
                            text = date_tag.get_text(strip=True)
                            if text and not text.isdigit() and "Wybierz" not in text and ":" not in text:
                                if any(x in text.lower() for x in ["związek", "liga", "klasa", "puchar", "grupa"]):
                                    current_league = text
                            continue

                        # Druga metoda wykrywania ligi (znacznik <b>)
                        league_tag = row.find("b")
                        if league_tag and not row.find("a") and not league_tag.get_text(strip=True).isdigit():
                            text_league = league_tag.get_text(strip=True)
                            if ":" not in text_league:
                                current_league = text_league
                                continue

                        # Wyciąganie konkretnego meczu
                        cols = row.find_all("td")
                        if len(cols) >= 2:
                            time_text = cols[0].get_text(strip=True)
                            
                            # Sprawdzenie czy pierwsza kolumna to godzina meczu (HH:MM)
                            if ":" in time_text and len(time_text) <= 5:
                                teams_text = cols[1].get_text(strip=True)
                                score_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                                
                                all_matches.append({
                                    "Data_Sort": celowana_data.date(),  # Klucz do poprawnego chronologicznego sortowania
                                    "Dzień": formatowana_data_pl,
                                    "Rozgrywki / Liga": current_league,
                                    "Godzina": time_text,
                                    "Mecz": teams_text,
                                    "Wynik": score_text
                                })
            
            # Bezpiecznik: odpoczynek 0.1s dla serwera przed kolejnym zapytaniem
            time.sleep(0.1)

        except Exception:
            pass  # Ignorujemy błędy losowych dni, aby pobrać resztę

    # Czyszczenie elementów paska postępu po zakończeniu pętli
    progress_bar.empty()
    status_text.empty()

    df = pd.DataFrame(all_matches)
    
    if not df.empty:
        # Sortowanie: Dzień systemowy (chronologicznie), następnie Godzina meczu
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Data_Sort", "Sort_Time", "Rozgrywki / Liga"])
        
        # Usunięcie technicznych kolumn do sortowania
        df = df.drop(columns=['Data_Sort', 'Sort_Time'])
        
    return df

# 2. Renderowanie interfejsu użytkownika w Streamlit
try:
    df_mecze = pobierz_mecze_3_tygodnie()

    if df_mecze.empty:
        st.warning("Nie znaleziono zaplanowanych meczów w przeciągu najbliższych 3 tygodni na 90minut.pl.")
    else:
        # Dynamiczny filtr wyszukiwania na całą tabelę zbiorczą
        search_query = st.text_input("🔍 Filtruj wyniki (wpisz klub, ligę, województwo lub dzień tygodnia):", "")
        
        if search_query:
            df_mecze = df_mecze[df_mecze.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

        # Wyświetlenie interaktywnej tabeli
        st.dataframe(
            df_mecze,
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
    st.error(f"Wystąpił problem z działaniem aplikacji: {e}")

# Przycisk czyszczący cache i pobierający dane od nowa
if st.button("🔄 Odśwież i pobierz od nowa"):
    st.cache_data.clear()
    st.rerun()
