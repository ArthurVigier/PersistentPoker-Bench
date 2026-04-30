import json
import os
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pathlib import Path

def create_poker_video(jsonl_path: str, output_path: str):
    print(f"Reading data from {jsonl_path}...")
    
    hands_data = []
    
    with open(jsonl_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                match_data = json.loads(line)
                # Dans results.jsonl, la liste des mains est dans la clé 'transcript'
                hands = match_data.get("transcript", [])
                
                # On ajoute les mains à la suite
                for hand in hands:
                    # Dans le snapshot de la main, on cherche les infos de fin de main
                    pool_after = hand.get("persistent_pool_after", [])
                    hand_state = hand.get("hand_state", {})
                    variant = hand_state.get("variant", "unknown").upper()
                    winner_decision = hand.get("winner_pool_decision", "continue")
                    
                    hands_data.append({
                        "hand_num": len(hands_data) + 1,
                        "pool_size": len(pool_after),
                        "variant": variant,
                        "decision": winner_decision
                    })
            except json.JSONDecodeError:
                print("Skipping invalid JSON line.")
    
    if not hands_data:
        print("No hands found in this match.")
        return

    # Setup the plot
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#0b0f1a')
    ax.set_facecolor('#0b0f1a')
    ax.tick_params(colors='#e0e0e0')
    for spine in ax.spines.values():
        spine.set_color('#3d2b1f')

    ax.set_xlim(0, len(hands_data) + 1)
    ax.set_ylim(0, max(h["pool_size"] for h in hands_data) + 10)
    ax.set_title('PersistentPoker-Bench: The Cognitive Load Marathon', color='#f2b84b', fontsize=16, pad=20)
    ax.set_xlabel('Hand Number', color='#e0e0e0', fontsize=12)
    ax.set_ylabel('Cards in Persistent Pool', color='#e0e0e0', fontsize=12)

    line, = ax.plot([], [], color='#67d4c5', linewidth=3, marker='o', markersize=8, markerfacecolor='#ef6a6a')
    variant_text = ax.text(0.05, 0.90, '', transform=ax.transAxes, color='#f2b84b', fontsize=14, fontweight='bold')
    reset_text = ax.text(0.5, 0.5, '', transform=ax.transAxes, color='#ef6a6a', fontsize=24, fontweight='bold', ha='center', va='center', alpha=0)

    x_data, y_data = [], []

    def init():
        line.set_data([], [])
        variant_text.set_text('')
        reset_text.set_alpha(0)
        return line, variant_text, reset_text

    def update(frame):
        if frame < len(hands_data):
            current_hand = hands_data[frame]
            x_data.append(current_hand["hand_num"])
            y_data.append(current_hand["pool_size"])
            
            line.set_data(x_data, y_data)
            variant_text.set_text(f'Game: {current_hand["variant"]}')
            
            if current_hand["decision"] == "reset":
                reset_text.set_text('CLEARED BY RESET!')
                reset_text.set_alpha(1.0)
            else:
                reset_text.set_alpha(0)
                
            return line, variant_text, reset_text
        return line, variant_text, reset_text

    print(f"Generating animation with {len(hands_data)} frames...")
    ani = animation.FuncAnimation(fig, update, frames=len(hands_data)+5, init_func=init, blit=True, interval=500)

    try:
        # Save as MP4 using ffmpeg
        writer = animation.FFMpegWriter(fps=2, metadata=dict(artist='PersistentPoker-Bench'), bitrate=1800)
        ani.save(output_path, writer=writer)
        print(f"Video successfully saved to {output_path} ! 🎥")
    except Exception as e:
        print(f"Failed to save as MP4 (ffmpeg might be missing): {e}")
        # Fallback to GIF
        gif_path = output_path.replace('.mp4', '.gif')
        print(f"Attempting to save as GIF instead at {gif_path}...")
        ani.save(gif_path, writer='pillow', fps=2)
        print("GIF successfully saved!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="artifacts/infernal-marathon-40-hands/results.jsonl")
    parser.add_argument("--output", type=str, default="marathon_timelapse.mp4")
    args = parser.parse_args()
    
    create_poker_video(args.input, args.output)
