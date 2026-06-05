import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 1. Konfiguracja strony Streamlit
st.set_page_config(page_title="Terminarz 90minut.pl (WAP)", layout="wide", page_icon="⚽")

st.title("⚽ Specjalny parser meczów (WAP) - 90minut.pl")
st.caption("Aplikacja korzysta z uproszczonej wersji mobilnej 90minut, co całkowicie omija blokady IP i błędy proxy.")

@st.cache_data(ttl=300)  # Odświeżanie co 5 minut
def pobierz_mecze_wap():
    # Uderzamy bezpośrednio w wersję lite/wap - serwer jej nie blokuje
    url = "http://www.90minut.pl/wap/dzis.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        # Wersja WAP również ma kodowanie ISO-8859-2
        response.encoding = 'iso-8859-2'
        html_content = response.text
    except Exception as e:
        st.error(f"Błąd bezpośredniego połączenia: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(html_content, "html.parser")
    
    # W wersji WAP struktura opiera się na znacznikach <p> oraz liniach <br>
    paragraphs = soup.find_all("p")
    
    matches_data = []
    current_date = "Dziś"
    current_league = "Inne / Nieznane"

    for p in paragraphs:
        text = p.get_text("\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        for line in lines:
            # 1. Wykrywanie daty (np. "6 czerwca 2026 (piątek)")
            if "wypisz_zapowiedzi" in str(p) or ("(" in line and ")" in line and any(m in line.lower() for m in ["stycz", "lut", "mar", "kwie", "maj", "czer", "lip", "sier", "wrze", "paź", "list", "grud"])):
                current_date = line
                continue
            
            # 2. Wykrywanie ligi (w wersji WAP ligi są często pisane WIELKIMI LITERAMI lub kończą się na ":" albo są w osobnym bloku)
            if line.isupper() and len(line) > 3 and not line.startswith(("0", "1", "2")):
                current_league = line
                continue
                
            # 3. Wykrywanie meczu - linia musi zaczynać się od godziny (np. "18:00 Mecz - Klub")
            if ":" in line and line[0].isdigit():
                try:
                    # Podział na godzinę i resztę tekstu
                    parts = line.split(" ", 1)
                    time_text = parts[0].strip()
                    rest_text = parts[1].strip() if len(parts) > 1 else ""
                    
                    # Wyciąganie wyniku, jeśli istnieje (często na końcu w nawiasie lub po myślniku)
                    score_text = ""
                    if " - " in rest_text:
                        # Próba oddzielenia meczu od wyniku, jeśli to wersja live
                        match_parts = rest_text.split("  ") # WAP często daje podwójną spację przed wynikiem
                        if len(match_parts) > 1:
                            teams_text = match_parts[0].strip()
                            score_text = match_parts[1].strip()
                        else:
                            teams_text = rest_text
                    else:
                        teams_text = rest_text

                    if len(time_text) <= 5:
                        matches_data.append({
                            "Data": current_date,
                            "Rozgrywki / Związek": current_league,
                            "Godzina": time_text,
                            "Mecz": teams_text,
                            "Wynik": score_text
                        })
                except Exception:
                    continue

    df = pd.DataFrame(matches_data)
    
    if not df.empty:
        # Sortowanie chronologiczne według czasu
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Data", "Sort_Time", "Rozgrywki / Związek"])
        df = df.drop(columns=['Sort_Time'])
        
    return df

# 2. Renderowanie interfejsu Streamlit
try:
    with st.spinner('Pobieram dane z mobilnego serwera 90minut...'):
        df_mecze = pobierz_mecze_wap()

    if df_mecze.empty:
        st.error("Serwer WAP zwrócił pustą stronę. Prawdopodobnie brak zaplanowanych meczów w tym momencie lub chwilowa przerwa techniczna.")
    else:
        # Wyszukiwarka klubów/lig
        search_query = st.text_input("🔍 Szybkie filtrowanie tabeli:", "")
        if search_query:
            df_mecze = df_mecze[df_mecze.apply(lambda row: search_query.lower() in row.astype(str).str.lower().values, axis=1)]

        # Wyświetlenie tabeli
        st.dataframe(
            df_mecze,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Data": st.column_config.TextColumn("Dzień", width="medium"),
                "Rozgrywki / Związek": st.column_config.TextColumn("Rozgrywki", width="medium"),
                "Godzina": st.column_config.TextColumn("Godzina", width="small"),
                "Mecz": st.column_config.TextColumn("Spotkanie", width="large"),
                "Wynik": st.column_config.TextColumn("Wynik", width="small"),
            }
        )

except Exception as e:
    st.error(f"Błąd aplikacji: {e}")

if st.button("🔄 Odśwież"):
    st.cache_data.clear()
    st.rerun()
