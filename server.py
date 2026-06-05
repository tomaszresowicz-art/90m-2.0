import http.server
import socketserver
import json
import requests
import time
import webbrowser
import threading
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Ustawienia serwera
PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Obsługa żądania pobrania danych
        if self.path.startswith('/pobierz'):
            try:
                id_okreg = self.path.split('?id=')[1]
                print(f"Otrzymano żądanie dla okręgu ID: {id_okreg}")
                dane = self.pobierz_dane(id_okreg)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(dane).encode('utf-8'))
            except Exception as e:
                print(f"BŁĄD W POBIERANIU: {e}")
        else:
            # Serwowanie plików statycznych (np. interface.html)
            super().do_GET()

    def pobierz_dane(self, id_okreg):
        wyniki = []
        dni_tyg = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
        
        # Mapowanie miesięcy na język polski
        miesiac_map = {
            "01": "stycznia", "02": "lutego", "03": "marca", "04": "kwietnia",
            "05": "maja", "06": "czerwca", "07": "lipca", "08": "sierpnia",
            "09": "września", "10": "października", "11": "listopada", "12": "grudnia"
        }
        
        for i in range(14): # Pobieranie na 14 dni
            data = datetime.now() + timedelta(days=i)
            url = f"http://www.90minut.pl/mecze_okreg.php?id_okreg={id_okreg}&data={data.strftime('%Y-%m-%d')}"
            
            try:
                resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                soup = BeautifulSoup(resp.text, "html.parser")
                
                for tag in soup.find_all("b"):
                    if len(tag.text) == 5 and ":" in tag.text:
                        mecz = tag.next_sibling
                        # Formatowanie daty zgodnie z życzeniem: "5 czerwca (piątek)"
                        miesiac = miesiac_map.get(data.strftime('%m'), data.strftime('%B'))
                        
                        wyniki.append({
                            "data_sort": data.strftime('%Y-%m-%d'),
                            "data_label": f"{data.day} {miesiac} ({dni_tyg[data.weekday()]})",
                            "godzina": tag.text,
                            "mecz": mecz.text.strip() if hasattr(mecz, 'text') else str(mecz).strip()
                        })
            except Exception as e:
                print(f"Błąd sieciowy dla daty {data}: {e}")
        
        # Sortowanie: najpierw po dacie, potem po godzinie
        wyniki.sort(key=lambda x: (x['data_sort'], x['godzina']))
        return wyniki

# Funkcja uruchamiająca przeglądarkę
def otworz_strone():
    time.sleep(2)
    webbrowser.open(f"http://localhost:{PORT}/interface.html")

# Uruchomienie serwera
if __name__ == "__main__":
    threading.Thread(target=otworz_strone, daemon=True).start()
    print(f"Serwer działa na http://localhost:{PORT}")
    print("Naciśnij Ctrl+C aby zatrzymać.")
    
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        print(f"KRYTYCZNY BŁĄD SERWERA: {e}")
        input("Wciśnij ENTER aby zamknąć...")