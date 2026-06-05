from flask import Flask, jsonify, send_from_directory, request
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.')

# Mapowanie miesięcy
MIESIAC_MAP = {
    "01": "stycznia", "02": "lutego", "03": "marca", "04": "kwietnia",
    "05": "maja", "06": "czerwca", "07": "lipca", "08": "sierpnia",
    "09": "września", "10": "października", "11": "listopada", "12": "grudnia"
}
DNI_TYG = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]

@app.route('/')
def index():
    return send_from_directory('.', 'interface.html')

@app.route('/pobierz')
def pobierz():
    id_okreg = request.args.get('id')
    wyniki = []
    
    for i in range(14):
        data = datetime.now() + timedelta(days=i)
        url = f"http://www.90minut.pl/mecze_okreg.php?id_okreg={id_okreg}&data={data.strftime('%Y-%m-%d')}"
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all("b"):
                if len(tag.text) == 5 and ":" in tag.text:
                    mecz = tag.next_sibling
                    miesiac = MIESIAC_MAP.get(data.strftime('%m'), data.strftime('%B'))
                    wyniki.append({
                        "data_sort": data.strftime('%Y-%m-%d'),
                        "data_label": f"{data.day} {miesiac} ({DNI_TYG[data.weekday()]})",
                        "godzina": tag.text,
                        "mecz": mecz.text.strip() if hasattr(mecz, 'text') else str(mecz).strip()
                    })
        except: continue
    
    wyniki.sort(key=lambda x: (x['data_sort'], x['godzina']))
    return jsonify(wyniki)

if __name__ == '__main__':
    app.run()