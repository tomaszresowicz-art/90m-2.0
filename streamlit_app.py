import streamlit as st
import requests
import re
import pandas as pd

# 1. Konfiguracja strony Streamlit
st.set_page_config(page_title="Terminarz 90minut.pl", layout="wide", page_icon="⚽")

st.title("⚽ Pancerny Parser 90minut.pl")
st.caption("Ta wersja ignoruje strukturę HTML i wyciąga mecze bezpośrednio z tekstu za pomocą RegEx.")

@st.cache_data(ttl=300)
def pobierz_mecze_regex():
    # Próbujemy najpierw wersję mobilną (lżejsza i stabilniejsza)
    url = "http://www.90minut.pl/wap/dzis.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'iso-8859-2'
        text_content = response.text
    except Exception as e:
        st.error(f"Błąd połączenia: {e}")
        return pd.DataFrame()

    # Jeśli wersja WAP była pusta, awaryjnie sprawdzamy wersję główną
    if not text_content or len(text_content) < 500:
        try:
            url_main = "http://www.90minut.pl/dzis.php"
            response = requests.get(url_main, headers=headers, timeout=10)
            response.encoding = 'iso-8859-2'
            text_content = response.text
        except:
            pass

    # Usuwamy tagi HTML, żeby został sam czysty tekst strony
    clean_text = re.sub(r'<[^>]+>', '\n', text_content)
    lines = [line.strip() for line in clean_text.split('\n') if line.strip()]

    matches_data = []
    current_league = "Rozgrywki"
    current_date = "Dziś"

    # Wyrażenie regularne szukające godzin (np. 17:30 lub 9:00) na początku linii
    time_pattern = re.compile(r'^([0-2]?[0-9]:[0-5][0-9])\s+(.+)$')

    for line in lines:
        # Próba wykrycia nagłówka ligi (często pisany wielkimi literami, np. "I LIGA")
        if line.isupper() and len(line) > 5 and not line.startswith(("0", "1", "2")):
            current_league = line
            continue
            
        # Próba wykrycia nagłówka daty
        if "(" in line and ")" in line and any(m in line.lower() for m in ["stycz", "lut", "mar", "kwie", "maj", "czer", "lip", "sier", "wrze", "paź", "list", "grud"]):
            current_date = line
            continue

        # Szukanie meczu
        match = time_pattern.match(line)
        if match:
            godzina = match.group(1)
            reszta = match.group(2)
            
            # Podział na mecz i wynik (jeśli wynik już jest podany)
            wynik = ""
            if " - " in reszta:
                # Jeśli w linii są wyraźne cyfry wyniku, np. "Team A 2-1 Team B" lub "Team A  2-1"
                wynik_match = re.search(r'(\d+-\d+|\d+:\d+)', reszta)
                if wynik_match:
                    wynik = wynik_match.group(1)
                    reszta = reszta.replace(wynik, "").strip()

            matches_data.append({
                "Data": current_date,
                "Rozgrywki / Związek": current_league,
                "Godzina": godzina,
                "Mecz": reszta,
                "Wynik": wynik
            })

    df = pd.DataFrame(matches_data)
    
    if not df.empty:
        # Sortowanie chronologiczne
        df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
        df = df.sort_values(by=["Data", "Sort_Time"])
        df = df.drop(columns=['Sort_Time'])
        
    return df

# 2. UI Streamlit
try:
    with st.spinner('Wyciągam mecze bezpośrednio z kodu źródłowego...'):
        df_mecze = pobierz_mecze_regex()

    if df_mecze.empty:
        st.error("Nadal nie udało się sparsować danych. Prawdopodobnie serwer 90minut całkowicie blokuje ruch z tej domeny (zwraca kod błędu HTTP przed załadowaniem strony).")
        
        # Sekcja debugowania (pokaże nam co dokładnie widzi serwer)
        if st.checkbox("Pokaż logi debugowania (co widzi serwer?)"):
            try:
                res = requests.get("http://www.90minut.pl/wap/dzis.php", timeout=5)
                st.code(f"Status HTTP: {res.status_code}\n\nPierwsze 500 znaków odpowiedzi:\n{res.text[:500]}")
            except Exception as debug_err:
                st.code(f"Błąd połączenia debugowania: {debug_err}")
    else:
        search_query = st.text_input("🔍 Filtruj tabelę:", "")
        if search_query:
            df_mecze = df_mecze[df_mecze.apply(lambda row: search_query.lower() in row.astype(str).str.lower().values, axis=1)]

        st.dataframe(
            df_mecze,
            use_container_width=True,
            hide_index=True
        )

except Exception as e:
    st.error(f"Błąd aplikacji: {e}")

if st.button("🔄 Odśwież"):
    st.cache_data.clear()
    st.rerun()
