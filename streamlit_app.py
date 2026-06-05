import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 1. Ustawienia Streamlit
st.set_page_config(page_title="Terminarz 90minut.pl", layout="wide", page_icon="⚽")

st.title("⚽ Mecze z zakładki 'Dziś grają' (mecze_okreg.php)")
st.caption("Aplikacja pobiera dane z aktualnego adresu 90minut.pl i układa je chronologicznie.")

@st.cache_data(ttl=300)  # Cache na 5 minut
def pobierz_mecze_90minut():
    # Dokładnie ten adres, o którym wspomniałeś!
    url = "http://www.90minut.pl/mecze_okreg.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            st.error(f"Błąd HTTP: {response.status_code}")
            return pd.DataFrame()
            
        response.encoding = 'iso-8859-2'
        html_content = response.text
    except Exception as e:
        st.error(f"Błąd połączenia: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(html_content, "html.parser")
    
    # Szukamy tabeli głównej
    main_table = soup.find("table", {"class": "main"})
    if not main_table:
        st.error("Nie znaleziono głównej tabeli meczów. Sprawdź, czy serwer nie zwrócił błędu.")
        return pd.DataFrame()

    matches_data = []
    current_date = "Dziś"
    current_league = "Szczebel centralny"

    # Iteracja po wierszach tabeli
    for row in main_table.find_all("tr"):
        # 1. Szukamy nagłówka daty (w mecze_okreg często zawiera tekst ze związkiem i dniem)
        date_tag = row.find("th") or row.find("td", {"class": "vader"})
        if date_tag and "href" not in str(date_tag):
            text = date_tag.get_text(strip=True)
            if text and not text.isdigit() and "Wybierz" not in text:
                current_date = text
                continue

        # 2. Szukamy nagłówka ligi (pogrubiony tekst <b>, zazwyczaj bez linków)
        league_tag = row.find("b")
        if league_tag and not row.find("a") and not league_tag.get_text(strip=True).isdigit():
            text_league = league_tag.get_text(strip=True)
            if ":" not in text_league:  # Żeby nie pomylić z godziną meczu
                current_league = text_league
                continue

        # 3. Wyciągamy informacje o meczu
        cols = row.find_all("td")
        if len(cols) >= 2:
            time_text = cols[0].get_text(strip=True)
            
            # Sprawdzamy czy pierwsza kolumna to faktycznie godzina (np. "17:00")
            if ":" in time_text and len(time_text) <= 5:
                teams_text = cols[1].get_text(strip=True)
                
                # Jeśli jest trzecia kolumna, to może być tam wynik
                score_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                
                matches_data.append({
                    "Dzień / Okręg": current_date,
                    "Rozgrywki / Liga": current_league,
                    "Godzina": time_text,
                    "Mecz": teams_text,
                    "Wynik": score_text
                })

    df = pd.DataFrame(matches_data)
    
    if not df.empty:
        # Sortowanie chronologiczne według godzin
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Dzień / Okręg", "Sort_Time", "Rozgrywki / Liga"])
        df = df.drop(columns=['Sort_Time'])
        
    return df

# Wyświetlanie UI
try:
    with st.spinner('Pobieram aktualne mecze z mecze_okreg.php...'):
        df_mecze = pobierz_mecze_90minut()

    if df_mecze.empty:
        st.warning("Brak zaplanowanych meczów na liście lub problem z dopasowaniem tabeli.")
    else:
        search_query = st.text_input("🔍 Filtruj wyniki (klub, liga, region):", "")
        if search_query:
            df_mecze = df_mecze
