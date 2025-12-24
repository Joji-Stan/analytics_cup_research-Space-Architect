import pandas as pd
import numpy as np
from scipy.spatial import distance

def get_zone_weight(x: float, y: float) -> float:
    """
    Définit la 'valeur tactique' de la position (xPRA Weight).
    Terrain SkillCorner : 105x68.
    """
    weight = 1.0
    
    # 1. PONDÉRATION LONGITUDINALE (X) - Dangerosité
    if x > 70:
        weight = 3.0  # Zone de Finition
    elif x > 35:
        weight = 1.5  # Zone de Progression
        
    # 2. PONDÉRATION LATÉRALE (Y) - Bonus Axe (Golden Zone)
    # Centre Y=34. Zone 24-44.
    if 24 <= y <= 44:
        weight *= 1.2
        
    return weight

def calculate_gaussian_pressure(frame_data: pd.DataFrame, carrier_id: int, team_id_possession: int, sigma: float = 3.0) -> float:
    """Calcule la Pression Gaussienne (Continue) autour du porteur."""
    if frame_data.empty: return 0.0

    carrier = frame_data[frame_data['player_id'] == carrier_id]
    if carrier.empty: return 0.0 

    carrier_pos = carrier.iloc[0][['x', 'y']].values.astype(float).reshape(1, -1)

    opponents = frame_data[
        (frame_data['team_id'] != team_id_possession) &
        (frame_data['team_id'] != -1) &
        (frame_data['player_id'] != -1)
    ]

    if opponents.empty: return 0.0

    opponents_pos = opponents[['x', 'y']].values.astype(float)
    dists = distance.cdist(carrier_pos, opponents_pos)[0]
    
    # Influence Gaussienne
    pressure_values = np.exp(- (dists**2) / (2 * sigma**2))
    return float(np.sum(pressure_values))

def calculate_pressure_relief(tracking_df: pd.DataFrame, run_event: pd.Series) -> float:
    """Calcule le xPRA (Expected Pressure Relief Added)."""
    start_frame = run_event['frame_start']
    end_frame = run_event['frame_end']
    team_id = int(run_event['team_id'])
    
    try:
        carrier_id = int(run_event.get('player_in_possession_id', -1))
    except (ValueError, TypeError):
        return 0.0 

    if carrier_id == -1: return 0.0

    data_start = tracking_df[tracking_df['frame'] == start_frame]
    data_end = tracking_df[tracking_df['frame'] == end_frame]

    # Delta Physique
    p_start = calculate_gaussian_pressure(data_start, carrier_id, team_id, sigma=3.0)
    p_end = calculate_gaussian_pressure(data_end, carrier_id, team_id, sigma=3.0)
    raw_pra = p_start - p_end
    
    # Multiplicateur Tactique
    carrier_start = data_start[data_start['player_id'] == carrier_id]
    if not carrier_start.empty:
        cx = carrier_start.iloc[0]['x']
        cy = carrier_start.iloc[0]['y']
        zone_multiplier = get_zone_weight(cx, cy)
    else:
        zone_multiplier = 1.0

    return raw_pra * zone_multiplier