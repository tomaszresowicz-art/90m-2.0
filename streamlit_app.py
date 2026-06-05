import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 1. Konfiguracja strony Streamlit
st.set_page_config(page_title="Terminarz 90minut.pl", layout="wide", page_icon="⚽")

st.title("⚽ Terminarz meczów – 90minut.pl")
st.caption("Aplikacja pobiera dane bezpośrednio ze strony głównej przy użyciu zaawansowanego maskowania przeglądarki.")

@st.cache_data(ttl=300)  # Odświeżanie danych co 5 minut
def pobierz_mecze_90minut():
    url = "http://www.90minut.pl/dzis.php"
    
    # Kompletny zestaw nagłówków udający prawdziwą, fizyczną przeglądarkę
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }

    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            st.error(f"Serwer zwrócił błąd HTTP: {response.status_code}")
            return pd.DataFrame(), response.text[:500]
            
        response.encoding = 'iso-8859-2'
        html_content = response.text
    except Exception as e:
        st.error(f"Błąd krytyczny połączenia: {e}")
        return pd.DataFrame(), str(e)

    soup = BeautifulSoup(html_content, "html.parser")
    main_table = soup.find("table", {"class": "main"})

    if not main_table:
        return pd.DataFrame(), html_content[:500]

    matches_data = []
    current_date = "Dziś"
    current_league = "Inne / Nieznane"

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
        
    return df, None

# 2. Renderowanie UI Streamlit
try:
    with st.spinner('Łączenie z serwerem głównym 90minut.pl...'):
        df_mecze, debug_info = pobierz_mecze_90minut()

    if df_mecze.empty:
        st.warning("Nie znaleziono meczów lub strona zablokowała żądanie.")
        if debug_info:
            with st.expander("Szczegóły techniczne (Debug)"):
                st.code(debug_info)
    else:
        search_query = st.text_input("🔍 Filtruj wyniki (klub lub liga):", "")
        if search_query:
            df_mecze = df_mecze[df_mecze.apply(lambda row: search_query.lower() in row.astype(str).str.lower().values, axis=1)]

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
    st.error(f"Błąd aplikacji: {e}")

if st.button("🔄 Odśwież dane"):
    st.cache_data.clear()
    st.rerun()
