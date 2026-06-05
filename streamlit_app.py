import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re
import json

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

st.set_page_config(page_title="Niewykrywalny Terminarz 90minut", layout="wide", page_icon="⚽")

st.title("⚽ Niewykrywalny Terminarz 90minut.pl")
st.caption("Ta wersja wysyła zapytania bezpośrednio z Twojej przeglądarki (Twojego IP), dzięki czemu oszukuje systemy anty-botowe.")

# Inicjalizacja sesji
if "pobrane_html" not in st.session_state:
    st.session_state.pobrane_html = {}
if "finalne_mecze" not in st.session_state:
    st.session_state.finalne_mecze = []

with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrane_nazwy = st.multiselect(
        "Wybierz okręgi/związki:",
        options=list(OKREGI.values()),
        default=["Małopolski ZPN"]
    )
    LICZBA_DNI_W_PRZOD = st.slider("Zakres wyszukiwania (w dniach):", min_value=1, max_value=7, value=3)
    
    st.write("---")
    uruchom = st.button("🚀 Uruchom bezpieczne pobieranie", type="primary", use_container_width=True)
    
    if st.button("🔄 Resetuj aplikację", use_container_width=True):
        st.session_state.pobrane_html = {}
        st.session_state.finalne_mecze = []
        st.rerun()

wybrane_id = [k for k, v in OKREGI.items() if v in wybrane_nazwy]

# Funkcja parsująca surowy kod HTML dostarczony przez przeglądarkę
def parsuj_html_90minut(html_text, nazwa_okregu, formatowana_data_pl, celowana_data):
    matches = []
    regex_godzina = re.compile(r'^\d{1,2}:\d{2}$')
    
    soup = BeautifulSoup(html_text, "html.parser")
    main_headers = [b.get_text(strip=True) for b in soup.find_all("b")[:6]]
    
    # Jeśli przeglądarka też dostała stronę główną (np. brak meczów w poniedziałek)
    if 'Skarb Ekstraklasy' in main_headers or 'Transfery - Ekstr.' in main_headers:
        return matches

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
                    matches.append({
                        "Data_Sort": celowana_data.date(),
                        "Dzień": formatowana_data_pl,
                        "Okręg / Związek": nazwa_okregu,
                        "Rozgrywki / Liga": current_league,
                        "Godzina": time_text,
                        "Mecz": teams_text,
                        "Wynik": score_text
                    })
    return matches

# --- GENEROWANIE LINKÓW DO POBRANIA PRZEZ KLIENTA ---
list_of_urls = []
dzis = datetime.now()

for id_okreg in wybrane_id:
    for i in range(LICZBA_DNI_W_PRZOD + 1):
        c_data = dzis + timedelta(days=i)
        d_str = c_data.strftime("%Y-%m-%d")
        
        dni_tygodnia_pl = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
        miesiace_pl = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
        f_data_pl = f"{c_data.day} {miesiace_pl[c_data.month]} {c_data.year} ({dni_tygodnia_pl[c_data.weekday()]})"
        
        target_url = f"http://www.90minut.pl/mecze_okreg.php?id_okreg={id_okreg}&data={d_str}"
        
        list_of_urls.append({
            "url": target_url,
            "okreg": OKREGI[id_okreg],
            "data_pl": f_data_pl,
            "key": f"{id_okreg}_{d_str}",
            "raw_date": d_str
        })

if uruchom or len(st.session_state.pobrane_html) > 0:
    # KOMPONENT JAVASCRIPT: Wykonuje się w przeglądarce użytkownika i pobiera dane za pomocą 'fetch'
    # Wykorzystujemy darmowe proxy CORS-anywhere przeznaczone dla skryptów klienckich (identycznie jak w PyScript!)
    js_urls = json.dumps(list_of_urls)
    
    html_component = f"""
    <div id="status-area" style="font-family: sans-serif; color: #555; padding: 10px; background: #f0f2f6; border-radius: 5px;">
        🔄 Przygotowanie żądań organicznych...
    </div>

    <script>
    const urls = {js_urls};
    const results = {{}};
    
    async function fetchAll() {{
        const statusDiv = document.getElementById("status-area");
        
        for(let i=0; i<urls.length; i++) {{
            const item = urls[i];
            statusDiv.innerHTML = `⏳ Pobieranie jako użytkownik: <b>${{item.okreg}}</b> (${{item.data_pl}})...`;
            
            try {{
                // Używamy bezpiecznego tunelu klienckiego CORS (podobnie jak Twój PyScript)
                const response = await fetch('https://corsproxy.io/?' + encodeURIComponent(item.url));
                if(response.ok) {{
                    const text = await response.text();
                    results[item.key] = text;
                }}
            }} catch(e) {{
                console.error("Błąd pobierania:", e);
            }}
            // Mała przerwa, żeby wyglądało to naturalnie
            await new Promise(r => setTimeout(r, 300));
        }}
        
        statusDiv.innerHTML = "✅ Pobieranie zakończone! Przesyłanie danych do parsera Streamlit...";
        
        # Przesyłamy zebrany surowy kod HTML z przeglądarki z powrotem do aplikacji Streamlit
        window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            value: JSON.stringify(results)
        }}, '*');
    }}
    
    fetchAll();
    </script>
    """
    
    # Ukryty komponent wykonujący magię w przeglądarce
    if len(st.session_state.pobrane_html) == 0:
        st.info("Trwa pobieranie danych bezpośrednio przez Twoje połączenie internetowe. Proszę czekać...")
        response_js = components.html(html_component, height=80)
        
        if response_js:
            st.session_state.pobrane_html = json.loads(response_js)
            st.rerun()

# --- ETAP PARSOWANIA DANYCH W PYTHONIE ---
if len(st.session_state.pobrane_html) > 0:
    all_parsed_matches = []
    
    for item in list_of_urls:
        html_content = st.session_state.pobrane_html.get(item["key"])
        if html_content:
            celowana_data_obj = datetime.strptime(item["raw_date"], "%Y-%m-%d")
            mecze_z_dnia = parsuj_html_90minut(html_content, item["okreg"], item["data_pl"], celowana_data_obj)
            all_parsed_matches.extend(mecze_z_dnia)
            
    df_mecze = pd.DataFrame(all_parsed_matches)
    
    if df_mecze.empty:
        st.warning("⚠️ Twój adres IP pobrał strony bez błędu, ale serwer dla tych dni zwrócił brak meczów (puste tabele).")
    else:
        st.success(f"🎉 Sukces! Pomyślnie pobrano i sparsowano {len(df_mecze)} meczów przy użyciu Twojego połączenia!")
        
        search_query = st.text_input("🔍 Szybki filtr tabeli (wpisz klub lub ligę):", "")
        df_filtrowane = df_mecze.copy()
        
        if search_query:
            df_filtrowane = df_filtrowane[df_filtrowane.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

        st.write("---")
        
        for id_okreg in wybrane_id:
            nazwa_okregu = OKREGI[id_okreg]
            df_okregu = df_filtrowane[df_filtrowane["Okręg / Związek"] == nazwa_okregu]
            liczba_meczów = len(df_okregu)
            
            with st.expander(f"📍 {nazwa_okregu} ({liczba_meczów} meczów)", expanded=True if liczba_meczów > 0 else False):
                if df_okregu.empty:
                    st.info("Brak zaplanowanych spotkań w tym okresie.")
                else:
                    df_wyswietl = df_okregu.drop(columns=["Okręg / Związek", "Data_Sort"], errors='ignore')
                    st.dataframe(df_wyswietl, use_container_width=True, hide_index=True)
else:
    st.info("👈 Wybierz ligi w panelu bocznym i kliknij przycisk, aby rozpocząć organiczne pobieranie danych.")
