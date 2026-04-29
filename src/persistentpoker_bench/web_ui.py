from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import gradio as gr

from persistentpoker_bench.cards import cards_to_notation
from persistentpoker_bench.replay import (
    build_match_replay,
    replay_hand_choices,
    render_replay_hand_markdown,
    render_replay_summary_markdown,
)

# --- CSS CASINO WINAMAX-STYLE ---
LIVE_UI_CSS = """
:root {
    --ppb-bg: #0b0f1a;
    --ppb-table: #1a472a;
    --ppb-table-border: #3d2b1f;
    --ppb-gold: #f2b84b;
    --ppb-text: #e0e0e0;
}

.gradio-container {
    background-color: var(--ppb-bg) !important;
}

/* La Table de Poker Visuelle */
.poker-table-container {
    position: relative;
    width: 100%;
    max-width: 800px;
    height: 450px;
    background: radial-gradient(circle, #2d5a27 0%, #1a472a 100%);
    border: 12px solid var(--ppb-table-border);
    border-radius: 220px;
    box-shadow: inset 0 0 60px rgba(0,0,0,0.6), 0 20px 40px rgba(0,0,0,0.5);
    margin: 30px auto;
}

.poker-table-felt {
    position: absolute;
    top: 10px; left: 10px; right: 10px; bottom: 10px;
    border: 2px solid rgba(255,255,255,0.05);
    border-radius: 210px;
}

/* Community Cards au centre */
.community-cards-area {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 15px;
    z-index: 10;
}

.cards-row {
    display: flex;
    gap: 8px;
}

.pot-display {
    background: rgba(0,0,0,0.6);
    padding: 5px 15px;
    border-radius: 20px;
    color: var(--ppb-gold);
    font-weight: bold;
    font-size: 1.2em;
    border: 1px solid var(--ppb-gold);
}

/* Positions des Joueurs */
.player-seat {
    position: absolute;
    width: 120px;
    text-align: center;
    z-index: 20;
}

.seat-0 { bottom: -20px; left: 50%; transform: translateX(-50%); } 
.seat-1 { top: 50%; left: -60px; transform: translateY(-50%); }    
.seat-2 { top: -20px; left: 50%; transform: translateX(-50%); }    
.seat-3 { top: 50%; right: -60px; transform: translateY(-50%); }   

.player-avatar {
    background: #1c2331;
    border: 3px solid var(--ppb-gold);
    border-radius: 50%;
    width: 70px; height: 70px;
    margin: 0 auto 5px;
    display: flex; align-items: center; justify-content: center;
    font-weight: bold; font-size: 1.5em;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    color: white;
}

.player-info {
    background: rgba(18, 28, 38, 0.95);
    padding: 6px 10px;
    border-radius: 10px;
    font-size: 0.9em;
    color: white;
    border: 1px solid rgba(255,255,255,0.1);
}

.action-badge {
    position: absolute;
    top: -30px; left: 50%;
    transform: translateX(-50%);
    background: var(--ppb-gold);
    color: black;
    padding: 3px 12px;
    border-radius: 6px;
    font-weight: 900;
    font-size: 0.8em;
    text-transform: uppercase;
    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
}

/* Style des Cartes */
.ppb-card {
    display: inline-block;
    width: 42px;
    height: 60px;
    background: white;
    border-radius: 6px;
    color: black;
    font-weight: bold;
    text-align: center;
    line-height: 60px;
    font-size: 1.1em;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.4);
    border: 1px solid #ccc;
}

.ppb-card.hearts, .ppb-card.diamonds { color: #d12e2e; }
.ppb-card.clubs, .ppb-card.spades { color: #222; }

.ppb-card.hidden {
    background: linear-gradient(135deg, #203244 0%, #0b0f1a 100%);
    border: 1px solid var(--ppb-gold);
    color: transparent;
}
"""

def _card_to_html(card_str: str, is_hidden: bool = False) -> str:
    if card_str == "??" or is_hidden:
        return '<div class="ppb-card hidden">??</div>'
    
    suit_map = {"h": "hearts", "d": "diamonds", "c": "clubs", "s": "spades"}
    suit_icon = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
    
    rank = card_str[:-1]
    suit_code = card_str[-1].lower()
    suit_class = suit_map.get(suit_code, "")
    icon = suit_icon.get(suit_code, "")
    
    return f'<div class="ppb-card {suit_class}">{rank}{icon}</div>'

def render_visual_table(hand_data: dict[str, Any]) -> str:
    players = hand_data.get("players", [])
    community = hand_data.get("community_cards", [])
    pot = hand_data.get("pot_total", 0)
    variant = hand_data.get("variant", "holdem").upper()
    
    cards_html = "".join([_card_to_html(c) for c in community])
    
    players_html = ""
    for i, p in enumerate(players):
        seat_class = f"seat-{i}"
        status = p.get("status", "active")
        cards = p.get("hole_cards", ["??", "??"])
        
        # On ne montre les cartes que si la main est finie ou si c'est le vainqueur
        cards_display = "".join([_card_to_html(c, is_hidden=(status == "folded")) for c in cards])
        
        opacity = "opacity: 0.4;" if status == "folded" else ""
        
        players_html += f'''
        <div class="player-seat {seat_class}" style="{opacity}">
            <div class="player-avatar">{p["name"][0].upper()}</div>
            <div class="player-cards">{cards_display}</div>
            <div class="player-info">
                <strong>{p["name"]}</strong><br/>
                {p["stack"]} chips
            </div>
        </div>
        '''

    return f'''
    <div style="text-align:center; color: #f2b84b; font-weight: bold; font-size: 1.5em; margin-bottom: -20px;">{variant}</div>
    <div class="poker-table-container">
        <div class="poker-table-felt"></div>
        <div class="community-cards-area">
            <div class="pot-display">POT: {pot}</div>
            <div class="cards-row">{cards_html}</div>
        </div>
        {players_html}
    </div>
    '''

def build_web_app():
    with gr.Blocks(css=LIVE_UI_CSS, title="PersistentPoker-Bench Studio") as demo:
        gr.Markdown("# 🃏 PersistentPoker-Bench Replay Studio")
        
        with gr.Tab("Visual Replay Viewer"):
            with gr.Row():
                with gr.Column(scale=1):
                    file_input = gr.File(label="Drag & Drop results.jsonl here", file_types=[".jsonl", ".json"])
                    load_btn = gr.Button("🚀 Load Match", variant="primary")
                    demo_btn = gr.Button("🎲 Generate Dummy Demo", variant="secondary")
                    hand_selector = gr.Dropdown(label="Select Hand", choices=[])
                
                with gr.Column(scale=3):
                    table_display = gr.HTML(value='<div style="text-align:center; padding: 100px; color: #666;">Load a match to see the table</div>')
                    hand_summary = gr.Markdown()

        # État interne pour stocker les données du match chargé
        match_state = gr.State()

        def on_load_file(file):
            if file is None: return None, gr.update(choices=[]), "No file selected"
            try:
                # On supporte le format results.jsonl (on prend le premier match)
                with open(file.name, "r") as f:
                    first_line = f.readline()
                    data = json.loads(first_line)
                
                # Récupère les noms des mains pour le dropdown
                hand_names = [f"Hand {i+1}" for i in range(len(data.get("hand_results", [])))]
                return data, gr.update(choices=hand_names, value=hand_names[0] if hand_names else None), f"Match loaded: {len(hand_names)} hands."
            except Exception as e:
                return None, gr.update(choices=[]), f"Error loading file: {e}"

        def on_hand_change(hand_name, match_data):
            if not match_data or not hand_name: return "", ""
            hand_idx = int(hand_name.split(" ")[1]) - 1
            hand_result = match_data["hand_results"][hand_idx]
            
            # On prépare les données simplifiées pour le moteur de rendu visuel
            viz_data = {
                "variant": hand_result["hand_state"].get("variant", "holdem"),
                "pot_total": hand_result["hand_state"].get("pot_total", 0),
                "community_cards": hand_result["hand_state"].get("community_cards", []),
                "players": []
            }
            
            for i, p in enumerate(hand_result["hand_state"]["players"]):
                viz_data["players"].append({
                    "name": p["name"],
                    "stack": p["stack"],
                    "status": "folded" if p.get("folded") else "active",
                    "hole_cards": p.get("hole_cards", ["??", "??"])
                })
            
            # Rendu du Markdown textuel en dessous
            markdown_summary = render_replay_hand_markdown(hand_result)
            
            return render_visual_table(viz_data), markdown_summary

        def on_generate_demo():
            demo_path = Path("marathon_demo.jsonl")
            if not demo_path.exists():
                return None, gr.update(choices=[]), "Demo file 'marathon_demo.jsonl' not found on the server."
            try:
                with open(demo_path, "r") as f:
                    first_line = f.readline()
                    data = json.loads(first_line)
                
                hand_names = [f"Hand {i+1}" for i in range(len(data.get("hand_results", [])))]
                return data, gr.update(choices=hand_names, value=hand_names[0] if hand_names else None), f"Demo Marathon loaded: {len(hand_names)} hands."
            except Exception as e:
                return None, gr.update(choices=[]), f"Error loading demo file: {e}"

        demo_btn.click(on_generate_demo, inputs=[], outputs=[match_state, hand_selector, hand_summary])
        load_btn.click(on_load_file, inputs=[file_input], outputs=[match_state, hand_selector, hand_summary])
        hand_selector.change(on_hand_change, inputs=[hand_selector, match_state], outputs=[table_display, hand_summary])

    return demo

if __name__ == "__main__":
    build_web_app().launch()
