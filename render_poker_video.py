import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
import argparse
from pathlib import Path

def get_suit_color(card):
    if card == "??": return 'gray'
    s = card[-1].lower()
    return 'red' if s in ('h', 'd') else 'black'

def get_suit_symbol(card):
    if card == "??": return "?"
    s = card[-1].lower()
    symbols = {'h': '♥', 'd': '♦', 'c': '♣', 's': '♠'}
    return symbols.get(s, '')

def draw_card(ax, x, y, card, is_hidden=False):
    if is_hidden or card == "??":
        rect = patches.Rectangle((x, y), 0.6, 0.9, facecolor='#203244', edgecolor='#f2b84b', zorder=3)
        ax.add_patch(rect)
        ax.text(x + 0.3, y + 0.45, '?', color='white', ha='center', va='center', fontsize=12, zorder=4)
        return
    
    rect = patches.Rectangle((x, y), 0.6, 0.9, facecolor='white', edgecolor='#cccccc', zorder=3)
    ax.add_patch(rect)
    
    color = get_suit_color(card)
    symbol = get_suit_symbol(card)
    rank = card[:-1]
    
    ax.text(x + 0.3, y + 0.45, f"{rank}\n{symbol}", color=color, ha='center', va='center', fontsize=10, fontweight='bold', zorder=4)

def generate_video(jsonl_path: str, output_path: str):
    print(f"Reading {jsonl_path}...")
    
    hands = []
    with open(jsonl_path, 'r') as f:
        for line in f:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                hands.extend(data.get("transcript", []))
            except:
                continue

    if not hands:
        print("No valid hands found.")
        return

    # Extract distinct end-of-hand states (where winner_pool_decision is present)
    end_states = []
    for h in hands:
        if "winner_pool_decision" in h:
            end_states.append(h)
            
    if not end_states:
        print("No completed hands found to animate.")
        return

    print(f"Animating {len(end_states)} hands...")

    fig, ax = plt.subplots(figsize=(12, 8), facecolor='#0b0f1a')
    
    def update(frame):
        ax.clear()
        ax.set_facecolor('#0b0f1a')
        ax.set_xlim(-5, 5)
        ax.set_ylim(-4, 4)
        ax.axis('off')
        
        state = end_states[frame].get("hand_state", {})
        variant = state.get("variant", "UNKNOWN").upper()
        pot = state.get("pot_total", 0)
        pool = end_states[frame].get("persistent_pool_after", [])
        players = state.get("players", [])

        # Draw Table
        table = patches.Ellipse((0, 0), width=9, height=6, facecolor='#1a472a', edgecolor='#3d2b1f', lw=8, zorder=1)
        ax.add_patch(table)
        felt = patches.Ellipse((0, 0), width=8.7, height=5.7, facecolor='none', edgecolor=(1, 1, 1, 0.1), lw=2, zorder=2)
        ax.add_patch(felt)

        # Title & Info
        ax.text(0, 3.5, f"Hand {frame+1} - {variant}", color='#f2b84b', ha='center', fontsize=16, fontweight='bold')
        ax.text(0, 0.8, f"POT: {pot}", color='white', ha='center', fontsize=14, bbox=dict(facecolor='black', alpha=0.6, edgecolor='#f2b84b', boxstyle='round,pad=0.5'))
        ax.text(0, -1.8, f"Pool Size: {len(pool)} cards", color='white', ha='center', fontsize=12)

        # Draw Community Cards (Persistent Pool limit to last 10 for visibility)
        visible_pool = pool[-12:] if len(pool) > 12 else pool
        start_x = - (len(visible_pool) * 0.7) / 2
        for i, card in enumerate(visible_pool):
            draw_card(ax, start_x + (i * 0.7), -0.5, card)

        # Player Positions
        positions = [
            (0, -3.2, 'bottom'), # Seat 0
            (-3.8, 0, 'left'),   # Seat 1
            (0, 2.5, 'top'),     # Seat 2
            (3.8, 0, 'right')    # Seat 3
        ]

        for i, p in enumerate(players):
            if i >= len(positions): break
            px, py, align = positions[i]
            
            name = p.get("name", f"Seat {i}")
            stack = p.get("stack", 0)
            status = "Folded" if p.get("folded") else "Active"
            cards = p.get("hole_cards", ["??", "??"])
            
            alpha = 0.4 if status == "Folded" else 1.0
            
            ax.text(px, py - 0.7 if align == 'top' else py + 1.0, f"{name}\n{stack} chips", color='white', ha='center', va='center', fontsize=10, alpha=alpha, bbox=dict(facecolor='#121c26', edgecolor='white', alpha=0.8*alpha, boxstyle='round,pad=0.3'))
            
            c_start_x = px - (len(cards) * 0.35)
            for j, card in enumerate(cards):
                draw_card(ax, c_start_x + (j * 0.7), py, card, is_hidden=(status == "Folded"))

    ani = animation.FuncAnimation(fig, update, frames=len(end_states), interval=1000)
    
    try:
        writer = animation.FFMpegWriter(fps=1, metadata=dict(artist='PersistentPoker'), bitrate=1800)
        ani.save(output_path, writer=writer)
        print(f"✅ Video saved to {output_path}")
    except Exception as e:
        print(f"FFMpeg failed: {e}. Falling back to GIF...")
        gif_path = output_path.replace('.mp4', '.gif')
        ani.save(gif_path, writer='pillow', fps=1)
        print(f"✅ GIF saved to {gif_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="artifacts/infernal-marathon-40-hands/results.jsonl")
    parser.add_argument("--output", type=str, default="marathon_poker.mp4")
    args = parser.parse_args()
    generate_video(args.input, args.output)
