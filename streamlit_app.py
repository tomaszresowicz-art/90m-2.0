import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re
import json
import urllib.parse
import base64

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
st.caption("Aplikacja dostosowana do standardów Streamlit (st.iframe + st.query_params).")

# Panel boczny (Sidebar)
with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrane_nazwy = st.multiselect(
        "Wybierz okręgi/związki:",
        options=list(OKREGI.values()),
        default=["Małopolski ZPN"]
    )
    LICZBA_DNI_W_PRZOD = st.slider("Zakres wyszukiwania (w dniach):", min_value=1, max_value=7, value=3)
    
    st.write("---")
    uruchom = st.button("🚀 Uruchom pobieranie", type="primary", use_container_width=True)
    
    if st.button("🔄 Resetuj aplikację / Wyczyść dane", use_container_width=True):
        st.query_params.clear()
        st.cache_data.clear()
        st.rerun()

wybrane_id = [k for k, v in OKREGI.items() if v in wybrane_nazwy]

# Funkcja parsująca surowy kod HTML
def parsuj_html_90minut(html_text, nazwa_okregu, formatowana_data_pl, celowana_data):
    matches = []
    regex_godzina = re.compile(r'^\d{1,2}:\d{2}$')
    
    soup = BeautifulSoup(html_text, "html.parser")
    main_headers = [b.get_text(strip=True) for b in soup.find_all("b")[:6]]
    
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

# Przygotowanie listy URL
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

# Odczyt danych zapisanych w pasku adresu URL
dane_z_url = st.query_params.get("paczka_wynikowa", "")

if uruchom and not dane_z_url:
    js_urls = json.dumps(list_of_urls)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; padding:0; font-family: sans-serif; background: #e1f5fe;">
        <div id="loader-info" style="font-size: 13px; color: #1f77b4; padding: 10px; border-left: 4px solid #03a9f4;">
            🤖 Uruchamianie bezpiecznego tunelu...
        </div>

        <script>
        const urls = {js_urls};
        const results = {{}};
        
        async function run() {{
            const loader = document.getElementById("loader-info");
            
            for(let i=0; i<urls.length; i++) {{
                const item = urls[i];
                loader.innerHTML = `⏳ Pobieranie z Twojego IP: <b>${{item.okreg}}</b> (${{item.data_pl}})...`;
                
                try {{
                    const response = await fetch('https://corsproxy.io/?' + encodeURIComponent(item.url));
                    if(response.ok) {{
                        const text = await response.text();
                        results[item.key] = text;
                    }}
                }} catch(e) {{
                    console.error("Błąd pobierania:", e);
                }}
                await new Promise(r => setTimeout(r, 200));
            }}
            
            loader.innerHTML = "✅ Zakończono! Przeładowanie tabeli...";
            
            const jsonStr = JSON.stringify(results);
            const b64Data = btoa(unescape(encodeURIComponent(jsonStr)));
            
            const currentUrl = new URL(window.parent.location.href);
            currentUrl.searchParams.set("paczka_wynikowa", b64Data);
            window.parent.location.href = currentUrl.toString();
        }}
        
        setTimeout(run, 300);
        </script>
    </body>
    </html>
    """
    
    st.info("Trwa pobieranie terminarzy przez Twoją przeglądarkę...")
    st.iframe(src="data:text/html;charset=utf-8," + urllib.parse.quote(html_content), height=65)

# --- ETAP PRZETWARZANIA W PYTHONIE ---
if dane_z_url:
    try:
        decoded_bytes = base64.b64decode(dane_z_url)
        decoded_str = decoded_bytes.decode('utf-8')
        pobrane_strony = json.loads(decoded_str)
        
        all_parsed_matches = []
        
        for item in list_of_urls:
            html_content = pobrane_strony.get(item["key"])
            if html_content:
                celowana_data_obj = datetime.strptime(item["raw_date"], "%Y-%m-%d")
                mecze_z_dnia = parsuj_html_90minut(html_content, item["okreg"], item["data_pl"], celowana_data_obj)
                all_parsed_matches.extend(mecze_z_dnia)
                
        if len(all_parsed_matches) == 0:
            st.warning("⚠️ Połączenie powiodło się, ale w wybranym przedziale czasowym brak zaplanowanych meczów w bazie danych.")
        else:
            df_mecze = pd.DataFrame(all_parsed_matches)
            st.success(f"🎉 Sukces! Sparsowano {len(df_mecze)} meczów z Twojego organicznego adresu IP!")
            
            search_query = st.text_input("🔍 Filtruj wyniki (klub / liga):", "")
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
                        st.info("Brak spotkań.")
                    else:
                        df_wyswietl = df_okregu.drop(columns=["Okręg / Związek", "Data_Sort"], errors='ignore')
                        st.dataframe(df_wyswietl, use_container_width=True, hide_index=True)
                        
    except Exception as e:
        st.error(f"Nie udało się przetworzyć danych zwrotnych: {str(e)}")
        st.info("Jeśli błąd się powtarza, kliknij 'Resetuj aplikację' w panelu bocznym.")
else:
    if not uruchom:
        st.info("👈 Skonfiguruj filtry w panelu bocznym i kliknij '🚀 Uruchom pobieranie'.")
