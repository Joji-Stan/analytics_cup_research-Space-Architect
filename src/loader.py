import pandas as pd
import requests
import json
import io

# Standard files (Metadata, CSV Events) -> RAW
BASE_URL_MASTER = "https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches"
# Large files (Tracking JSONL) -> MEDIA (LFS)
BASE_URL_LFS = "https://media.githubusercontent.com/media/SkillCorner/opendata/master/data/matches"

MATCH_IDS = [
    '1886347', '2015213', '2013725', '2006229', '2011166', 
    '1996435', '2017461', '1925299', '1953632', '1899585'
]

def load_match_metadata(match_id: str):
    """Charge les métadonnées."""
    # Metadata is small -> RAW
    url = f"{BASE_URL_MASTER}/{match_id}/{match_id}_match.json"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.json()
    except: pass
    return None

def get_player_positions(match_id: str) -> dict:
    """Mappe les IDs joueurs vers leurs rôles (Defender, Midfielder...)"""
    meta = load_match_metadata(match_id)
    if not meta: return {}
    
    pos_map = {}
    # Structure SkillCorner OpenData: 'players' est top-level
    for p in meta.get('players', []):
        role = p.get('player_role', {}).get('name', 'Unknown')
        
        if 'Goalkeeper' in role: norm = 'GK'
        elif 'Back' in role or 'Defender' in role: norm = 'Defender'
        elif 'Midfield' in role or 'Winger' in role: norm = 'Midfielder'
        elif 'Forward' in role or 'Striker' in role: norm = 'Forward'
        else: norm = 'Unknown'
        
        pos_map[p['id']] = norm
    return pos_map

def get_player_teams(match_id: str) -> dict:
    """Mappe les IDs joueurs vers leur Team ID."""
    meta = load_match_metadata(match_id)
    if not meta: return {}
    
    team_map = {}
    for p in meta.get('players', []):
        if 'team_id' in p:
            team_map[p['id']] = int(p['team_id'])
    return team_map

def load_events(match_id: str):
    """Charge le CSV des événements."""
    # Events CSV is usually small -> RAW
    url = f"{BASE_URL_MASTER}/{match_id}/{match_id}_dynamic_events.csv"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return pd.read_csv(io.StringIO(r.text))
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ Erreur Events {match_id}: {e}")
        return pd.DataFrame()

def load_tracking_data(match_id: str):
    """
    Charge le tracking LFS via le CDN media.githubusercontent.
    """
    url = f"{BASE_URL_LFS}/{match_id}/{match_id}_tracking_extrapolated.jsonl"
    print(f"📡 Downloading LFS Tracking: {match_id}...")
    
    frames = {}
    try:
        # On utilise stream=True pour ne pas tout charger en RAM d'un coup
        with requests.get(url, stream=True) as r:
            if r.status_code != 200:
                print(f"❌ Erreur HTTP {r.status_code}")
                return {}
            
            # SÉCURITÉ LFS : On vérifie les premiers octets pour voir si c'est un pointeur texte
            # (Un vrai fichier JSONL commencera par '{', un pointeur par 'version https://git-lfs...')
            first_chunk = next(r.iter_content(chunk_size=50), b'')
            if b'version https://git-lfs' in first_chunk:
                print("❌ ERREUR CRITIQUE: Pointeur LFS détecté au lieu du fichier.")
                print("👉 Solution: Utiliser 'media.githubusercontent.com' (déjà fait normalement)")
                return {}
            
            # Si c'est bon, on traite le flux
            # On doit reconstruire le flux car on a consommé le début
            full_stream = io.BytesIO(first_chunk + r.raw.read())
            
            # Lecture ligne à ligne du buffer reconstruit
            # Note : C'est une simplification, pour de très gros fichiers > RAM, il faudrait chaîner les itérateurs.
            # Mais ici le fichier fait ~100Mo, ça passe en RAM.
            text_stream = io.TextIOWrapper(full_stream, encoding='utf-8')
            
            for line in text_stream:
                if line.strip():
                    try:
                        d = json.loads(line)
                        if 'player_data' in d:
                            frames[d['frame']] = d['player_data']
                    except:
                        continue
        return frames

    except Exception as e:
        print(f"❌ Erreur Tracking {match_id}: {e}")
        return {}