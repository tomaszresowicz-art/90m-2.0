import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re
import json
import urllib.parse

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

st.set_page_config(page_title="Półautomatyczny Terminarz 90minut", layout="wide", page_icon="⚽")

st.title("⚽ Niezawodny Terminarz 90minut.pl")
st.caption("Metoda hybrydowa: bezpieczne pobieranie przeglądarkowe + wczytanie pliku.")

# Panel boczny (Sidebar)
with st.sidebar:
    st.header("⚙️ Krok 1: Ustawienia pobierania")
    wybrane_nazwy = st.multiselect(
        "Wybierz okręgi/związki:",
        options=list(OKREGI.values()),
        default=["Małopolski ZPN"]
    )
    LICZBA_DNI_W_PRZOD = st.slider("Zakres wyszukiwania (w dniach):", min_value=1, max_value=7, value=3)
    
    st.write("---")
    st.header("⚙️ Krok 3: Czyszczenie")
    if st.button("🔄 Resetuj aplikację", use_container_width=True):
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
                        "Data_Sort": celowana_data.date().isoformat(),
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

# --- INTERFEJS KROK PO KROKU ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📥 Krok 1: Pobierz dane z 90minut")
    st.write("Kliknij poniższy przycisk. Otworzy się małe okienko, które pobierze mecze przez Twoje IP i zapisze plik `mecze_dane.json` w Twoim folderze Pobrane.")
    
    js_urls = json.dumps(list_of_urls)
    html_downloader = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body>
        <button id="btn" style="width:100%; height:45px; background-color:#ff4b4b; color:white; border:none; border-radius:8px; font-weight:bold; font-size:15px; cursor:pointer;">
            🚀 Uruchom pobieranie pliku z meczami
        </button>
        <div id="status" style="margin-top:10px; font-family:sans-serif; font-size:13px; color:#555;"></div>

        <script>
        document.getElementById('btn').addEventListener('click', async () => {{
            const urls = {js_urls};
            const results = {{}};
            const statusDiv = document.getElementById('status');
            
            document.getElementById('btn').disabled = true;
            document.getElementById('btn').style.backgroundColor = '#ccc';
            
            for(let i=0; i<urls.length; i++) {{
                const item = urls[i];
                statusDiv.innerHTML = `⏳ Pobieranie: ${{item.okreg}} (${{item.data_pl}})...`;
                
                try {{
                    const response = await fetch('https://corsproxy.io/?' + encodeURIComponent(item.url));
                    if(response.ok) {{
                        results[item.key] = await response.text();
                    }}
                }} catch(e) {{
                    console.error(e);
                }}
                await new Promise(r => setTimeout(r, 150));
            }}
            
            statusDiv.innerHTML = "✅ Gotowe! Generowanie pliku...";
            
            // Tworzenie i automatyczne pobieranie pliku JSON na komputer użytkownika
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(results));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", "mecze_dane.json");
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            
            statusDiv.innerHTML = "🎉 Plik 'mecze_dane.json' został pobrany! Przejdź do Kroku 2.";
            document.getElementById('btn').disabled = false;
            document.getElementById('btn').style.backgroundColor = '#ff4b4b';
        }});
        </script>
    </body>
    </html>
    """
    st.iframe(src="data:text/html;charset=utf-8," + urllib.parse.quote(html_downloader), height=110)

with col2:
    st.subheader("📤 Krok 2: Wgraj pobrany plik")
    st.write("Przeciągnij pobrany plik `mecze_dane.json` tutaj, aby Python wygenerował terminarz:")
    wgrany_plik = st.file_uploader("Wybierz plik JSON", type=["json"], label_visibility="collapsed")

# --- ETAP PRZETWARZANIA W PYTHONIE ---
if wgrany_plik is not None:
    try:
        pobrane_strony = json.load(wgrany_plik)
        all_parsed_matches = []
        
        for item in list_of_urls:
            html_content = pobrane_strony.get(item["key"])
            if html_content:
                celowana_data_obj = datetime.strptime(item["raw_date"], "%Y-%m-%d")
                mecze_z_dnia = parsuj_html_90minut(html_content, item["okreg"], item["data_pl"], celowana_data_obj)
                all_parsed_matches.extend(mecze_z_dnia)
                
        if len(all_parsed_matches) == 0:
            st.warning("⚠️ W załadowanym pliku nie odnaleziono żadnych zaplanowanych meczów dla wybranych kryteriów.")
        else:
            df_mecze = pd.DataFrame(all_parsed_matches)
            st.success(f"🎉 Sukces! Pomyślnie załadowano i sparsowano {len(df_mecze)} meczów!")
            
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
                        st.info("Brak spotkań spełniających kryteria.")
                    else:
                        df_wyswietl = df_okregu.drop(columns=["Okręg / Związek", "Data_Sort"], errors='ignore')
                        st.dataframe(df_wyswietl, use_container_width=True, hide_index=True)
                        
    except Exception as e:
        st.error(f"Błąd struktury pliku: {str(e)}")
else:
    st.info("💡 Instrukcja: Wybierz ligi, kliknij czerwony przycisk w Kroku 1, a otrzymany plik upuść w Kroku 2.")
