import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# 1. Pobieranie strony z odpowiednim User-Agent, żeby uniknąć blokady 403
url = "http://www.90minut.pl/dzis.php"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers)
    response.encoding = 'iso-8859-2'  # 90minut.pl używa kodowania ISO-8859-2
    html_content = response.text
except Exception as e:
    print(f"Błąd podczas pobierania strony: {e}")
    exit()

# 2. Parsowanie HTML za pomocą BeautifulSoup
soup = BeautifulSoup(html_content, "html.parser")
main_table = soup.find("table", {"class": "main"})

if not main_table:
    print("Nie znaleziono głównej tabeli meczów. Prawdopodobnie struktura strony się zmieniła lub zostałeś zablokowany.")
    exit()

matches_data = []
current_date = "Nieznana data"
current_league = "Nieznana liga"

# 3. Iteracja po wierszach tabeli i wyciąganie danych
for row in main_table.find_all("tr"):
    # Sprawdzamy czy wiersz to nagłówek z datą (np. "26 maja 2026 (wtorek)")
    date_tag = row.find("th") or row.find("td", {"class": "vader"})
    if date_tag and "href" not in str(date_tag):
        text = date_tag.get_text(strip=True)
        if text and not text.isdigit(): # Prosta walidacja nagłówka daty
            current_date = text
            continue

    # Sprawdzamy czy wiersz to nagłówek ligi/związku
    league_tag = row.find("b")
    if league_tag and not row.find("a"): # Nagłówki lig zazwyczaj nie mają linków w tym miejscu
        current_league = league_tag.get_text(strip=True)
        continue

    # Wyciąganie konkretnego meczu
    cols = row.find_all("td")
    if len(cols) >= 3:
        time_text = cols[0].get_text(strip=True)
        teams_text = cols[1].get_text(strip=True)
        score_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""

        # Format godziny to zazwyczaj "17:30" - odrzucamy wiersze, które nie są meczami
        if ":" in time_text and len(time_text) <= 5:
            matches_data.append({
                "Data": current_date,
                "Rozgrywki / Związek": current_league,
                "Godzina": time_text,
                "Mecz": teams_text,
                "Wynik": score_text
            })

# 4. Tworzenie DataFrame i sortowanie danych
df = pd.DataFrame(matches_data)

if df.empty:
    print("Brak meczów do wyświetlenia (No matches found).")
else:
    # Formatujemy godzinę do typu datetime, żeby sortowanie "od najwcześniejszego" działało poprawnie
    df['Sort_Time'] = pd.to_datetime(df['Godzina'], format='%H:%M', errors='coerce').dt.time
    
    # Sortowanie: najpierw Dzień (według kolejności pojawiania się), potem Rozgrywki, na końcu Godzina
    # Jeśli zależy Ci przede wszystkim na dniach i godzinach:
    df = df.sort_values(by=["Data", "Sort_Time", "Rozgrywki / Związek"])
    
    # Usuwamy kolumnę pomocniczą do sortowania
    df = df.drop(columns=['Sort_Time'])

    # 5. Generowanie tabeli HTML ze stylami CSS
    html_table = df.to_html(index=False, classes="matches-table")
    
    # Dodajemy podstawowy styl CSS, żeby tabelka wyglądała nowocześnie
    html_page = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Terminarz Matchy - 90minut</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; }}
            h2 {{ color: #333; }}
            .matches-table {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .matches-table th, .matches-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .matches-table th {{ background-color: #2c3e50; color: white; }}
            .matches-table tr:hover {{ background-color: #f1f1f1; }}
        </style>
    </head>
    <body>
        <h2>Dzisiejsze i nadchodzące mecze (Uporządkowane chronologicznie)</h2>
        {html_table}
    </body>
    </html>
    """

    # Zapis do pliku HTML
    with open("mecze.html", "w", encoding="utf-8") as f:
        f.write(html_page)
    
    print("Sukces! Wygenerowano plik mecze.html")