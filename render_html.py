import json
import argparse
from pathlib import Path

def generate_html(jsonl_path: str, output_path: str):
    # 1. Extraction des données
    match_data = None
    with open(jsonl_path, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    match_data = json.loads(line)
                    break # On prend le premier match valide
                except json.JSONDecodeError:
                    continue
                    
    if not match_data:
        print("No valid match found.")
        return

    hands = match_data.get("hand_results", [])
    if not hands: # Compatibilité avec un transcript plat si nécessaire
         hands = match_data.get("transcript", [])
         
    # 2. Nettoyage des données pour le JS
    clean_hands = []
    for h in hands:
        state = h.get("hand_state", {})
        clean_hands.append({
            "variant": state.get("variant", "HOLDEM").upper(),
            "pot": state.get("pot_total", 0),
            "community": state.get("community_cards", []),
            "players": [
                {
                    "name": p.get("name", "Unknown"),
                    "stack": p.get("stack", 0),
                    "status": "folded" if p.get("folded") else "active",
                    "cards": p.get("hole_cards", ["??", "??"])
                } for p in state.get("players", [])
            ]
        })

    hands_json = json.dumps(clean_hands)

    # 3. Le Template HTML/CSS/JS
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>PersistentPoker-Bench Replay</title>
        <style>
            body {{
                background-color: #0b0f1a;
                color: #e0e0e0;
                font-family: system-ui, sans-serif;
                margin: 0; padding: 20px;
                display: flex; flex-direction: column; align-items: center;
            }}
            .controls {{
                margin-bottom: 20px;
                display: flex; gap: 15px; align-items: center;
            }}
            button {{
                background: #f2b84b; color: #000; border: none;
                padding: 10px 20px; border-radius: 8px; font-weight: bold;
                cursor: pointer; font-size: 16px;
            }}
            button:hover {{ background: #d4af37; }}
            
            /* Table CSS */
            .poker-table-container {{
                position: relative; width: 800px; height: 450px;
                background: radial-gradient(circle, #2d5a27 0%, #1a472a 100%);
                border: 12px solid #3d2b1f; border-radius: 220px;
                box-shadow: inset 0 0 60px rgba(0,0,0,0.6), 0 20px 40px rgba(0,0,0,0.5);
                margin: 30px auto; font-size: 14px;
            }}
            .community-cards-area {{
                position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                display: flex; flex-direction: column; align-items: center; gap: 15px;
            }}
            .cards-row {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; max-width: 400px; }}
            .pot-display {{
                background: rgba(0,0,0,0.8); padding: 5px 15px; border-radius: 20px;
                color: #f2b84b; font-weight: bold; font-size: 1.2em; border: 1px solid #f2b84b;
            }}
            .player-seat {{ position: absolute; width: 120px; text-align: center; }}
            .seat-0 {{ bottom: -30px; left: 50%; transform: translateX(-50%); }} 
            .seat-1 {{ top: 50%; left: -60px; transform: translateY(-50%); }}    
            .seat-2 {{ top: -30px; left: 50%; transform: translateX(-50%); }}    
            .seat-3 {{ top: 50%; right: -60px; transform: translateY(-50%); }}   
            .player-avatar {{
                background: #1c2331; border: 3px solid #f2b84b; border-radius: 50%;
                width: 70px; height: 70px; margin: 0 auto 5px;
                display: flex; align-items: center; justify-content: center;
                font-weight: bold; font-size: 1.5em; color: white;
            }}
            .player-info {{
                background: rgba(18, 28, 38, 0.95); padding: 6px 10px; border-radius: 10px;
                color: white; border: 1px solid rgba(255,255,255,0.1);
            }}
            .ppb-card {{
                display: inline-block; width: 35px; height: 50px; background: white;
                border-radius: 4px; color: black; font-weight: bold; text-align: center;
                line-height: 50px; font-size: 1.1em; box-shadow: 2px 2px 6px rgba(0,0,0,0.4);
            }}
            .hearts, .diamonds {{ color: #d12e2e; }}
            .hidden {{ background: linear-gradient(135deg, #203244, #0b0f1a); border: 1px solid #f2b84b; color: transparent; }}
        </style>
    </head>
    <body>
        <h2>🏆 PersistentPoker-Bench Replay Viewer</h2>
        <div class="controls">
            <button onclick="prevHand()">◀ Previous</button>
            <h3 id="hand-label">Hand 1</h3>
            <button onclick="nextHand()">Next ▶</button>
        </div>
        
        <h3 id="variant-label" style="color:#f2b84b; margin-bottom:-10px;">HOLDEM</h3>
        <div class="poker-table-container" id="table-root"></div>

        <script>
            const hands = {hands_json};
            let currentIdx = 0;
            
            function getSuitIcon(card) {{
                if(card === "??") return "";
                const s = card.slice(-1).toLowerCase();
                if(s==='h') return '♥'; if(s==='d') return '♦';
                if(s==='c') return '♣'; if(s==='s') return '♠';
                return '';
            }}
            
            function getSuitClass(card) {{
                if(card === "??") return "hidden";
                const s = card.slice(-1).toLowerCase();
                if(s==='h') return 'hearts'; if(s==='d') return 'diamonds';
                return 'spades';
            }}

            function renderCard(card, isFolded) {{
                if(card === "??" || isFolded) return `<div class="ppb-card hidden">?</div>`;
                return `<div class="ppb-card ${{getSuitClass(card)}}">${{card.slice(0,-1)}}${{getSuitIcon(card)}}</div>`;
            }}

            function render() {{
                if(hands.length === 0) return;
                const hand = hands[currentIdx];
                document.getElementById('hand-label').innerText = `Hand ${{currentIdx + 1}} / ${{hands.length}}`;
                document.getElementById('variant-label').innerText = hand.variant;
                
                let commHtml = hand.community.map(c => renderCard(c, false)).join("");
                
                let playersHtml = hand.players.map((p, i) => {{
                    let isFolded = p.status === 'folded';
                    let op = isFolded ? 'opacity: 0.4;' : '';
                    let cardsHtml = p.cards.map(c => renderCard(c, isFolded)).join("");
                    return `
                    <div class="player-seat seat-${{i}}" style="${{op}}">
                        <div class="player-avatar">${{p.name[0]}}</div>
                        <div>${{cardsHtml}}</div>
                        <div class="player-info"><b>${{p.name}}</b><br/>${{p.stack}} chips</div>
                    </div>`;
                }}).join("");

                document.getElementById('table-root').innerHTML = `
                    <div class="community-cards-area">
                        <div class="pot-display">POT: ${{hand.pot}}</div>
                        <div class="cards-row">${{commHtml}}</div>
                    </div>
                    ${{playersHtml}}
                `;
            }}

            function nextHand() {{ if(currentIdx < hands.length - 1) {{ currentIdx++; render(); }} }}
            function prevHand() {{ if(currentIdx > 0) {{ currentIdx--; render(); }} }}
            
            render();
        </script>
    </body>
    </html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✅ Viewer successfully generated at: {output_path}")
    print("Double-click the file to open it in your browser!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="artifacts/infernal-marathon-40-hands/results.jsonl")
    parser.add_argument("--output", type=str, default="replay.html")
    args = parser.parse_args()
    generate_html(args.input, args.output)
