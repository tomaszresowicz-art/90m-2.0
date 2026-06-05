import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 1. Ustawienia wyglądu strony Streamlit
st.set_page_config(page_title="Terminarz 90minut.pl", layout="wide", page_icon="⚽")

st.title("⚽ Mecze z zakładki 'Dziś grają' (90minut.pl)")
st.caption("Aplikacja automatycznie pobiera, porządkuje i sortuje mecze chronologicznie.")

# Funkcja pobierająca dane - opakowana w cache, żeby nie odpytywać serwera za każdym kliknięciem użytkownika
@st.cache_data(ttl=600)  # Dane będą odświeżane maksymalnie co 10 minut
def pobierz_dane_90minut():
    url = "http://www.90minut.pl/dzis.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.encoding = 'iso-8859-2'
        html_content = response.text
    except Exception as e:
        st.error(f"Błąd podczas pobierania strony: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(html_content, "html.parser")
    main_table = soup.find("table", {"class": "main"})

    if not main_table:
        st.error("Nie znaleziono głównej tabeli meczów na stronie 90minut.pl.")
        return pd.DataFrame()

    matches_data = []
    current_date = "Nieznana data"
    current_league = "Nieznana liga"

    for row in main_table.find_all("tr"):
        # Wyciąganie daty
        date_tag = row.find("th") or row.find("td", {"class": "vader"})
        if date_tag and "href" not in str(date_tag):
            text = date_tag.get_text(strip=True)
            if text and not text.isdigit():
                current_date = text
                continue

        # Wyciąganie ligi / związku
        league_tag = row.find("b")
        if league_tag and not row.find("a"):
            current_league = league_tag.get_text(strip=True)
            continue

        # Wyciąganie meczu
        cols = row.find_all("td")
        if len(cols) >= 3:
            time_text = cols[0].get_text(strip=True)
            teams_text = cols[1].get_text(strip=True)
            score_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""

            if ":" in time_text and len(time_text) <= 5:
                matches_data.append({
                    "Data": current_date,
                    "Rozgrywki / Związek": current_league,
                    "Godzina": time_text,
                    "Mecz": teams_text,
                    "Wynik": score_text
                })

    df = pd.DataFrame(matches_data)
    
    if not df.empty:
        # Sortowanie chronologiczne
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Data", "Sort_Time", "Rozgrywki / Związek"])
        df = df.drop(columns=['Sort_Time'])
        
    return df

# 2. Logika wyświetlania w Streamlit
try:
    with st.spinner('Pobieram i sortuję mecze...'):
        df_mecze = pobierz_dane_90minut()

    if df_mecze.empty:
        st.warning("Obecnie brak meczów do wyświetlenia lub wystąpił problem z połączeniem.")
    else:
        # Interaktywne UI: Wyszukiwarka klubów/lig
        search_query = st.text_input("🔍 Filtruj mecze (wpisz nazwę drużyny lub ligi):", "")
        
        if search_query:
            df_mecze = df_mecze[df_mecze.apply(lambda row: search_query.lower() in row.astype(str).str.lower().values, axis=1)]

        # Wyświetlenie estetycznej tabeli w UI Streamlit
        st.dataframe(
            df_mecze,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Data": st.column_config.TextColumn("Dzień", width="medium"),
                "Rozgrywki / Związek": st.column_config.TextColumn("Liga / Związek", width="medium"),
                "Godzina": st.column_config.TextColumn("Godzina", width="small"),
                "Mecz": st.column_config.TextColumn("Spotkanie", width="large"),
                "Wynik": st.column_config.TextColumn("Wynik", width="small"),
            }
        )

except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd aplikacji: {e}")

# Przycisk do ręcznego wymuszenia odświeżenia danych
if st.button("🔄 Odśwież dane teraz"):
    st.cache_data.clear()
    st.rerun()
