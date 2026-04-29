import os
import json
from pathlib import Path
from huggingface_hub import HfApi, create_repo

def deploy():
    token = os.getenv("HF_TOKEN")
    if not token:
        print("HF_TOKEN not found in environment.")
        return

    api = HfApi(token=token)
    
    # Récupère l'utilisateur actuel pour nommer le repo
    user = api.whoami()["name"]
    repo_id = f"{user}/PersistentPoker-Bench"
    
    print(f"Targeting Space: https://huggingface.co/spaces/{repo_id}")

    # 1. Création du Space si besoin
    try:
        create_repo(repo_id=repo_id, token=token, repo_type="space", space_sdk="gradio", exist_ok=True)
        print(f"Space {repo_id} ready.")
    except Exception as e:
        print(f"Note on creation: {e}")

    # 2. Liste des fichiers à uploader
    # On upload src/, configs/, hf_space/, README.md, requirements.txt, pyproject.toml
    files_to_upload = []
    
    # Parcours des dossiers essentiels
    for folder in ["src", "configs", "hf_space"]:
        for path in Path(folder).rglob("*"):
            if path.is_file() and "__pycache__" not in str(path):
                files_to_upload.append(path)
                
    # Fichiers racine
    for f in ["README.md", "requirements.txt", "pyproject.toml"]:
        if Path(f).exists():
            files_to_upload.append(Path(f))

    print(f"Uploading {len(files_to_upload)} files...")
    
    # 3. Upload massif
    for file_path in files_to_upload:
        api.upload_file(
            path_or_fileobj=str(file_path),
            path_in_repo=str(file_path),
            repo_id=repo_id,
            repo_type="space",
        )

    # 4. Upload des résultats du Marathon pour la démo
    marathon_path = Path("artifacts/infernal-marathon-40-hands/decision_traces.jsonl")
    if marathon_path.exists():
        print("Uploading Marathon traces for public demo...")
        api.upload_file(
            path_or_fileobj=str(marathon_path),
            path_in_repo="marathon_demo.jsonl",
            repo_id=repo_id,
            repo_type="space",
        )

    print("Deployment complete! Your Space is building.")

if __name__ == "__main__":
    deploy()
