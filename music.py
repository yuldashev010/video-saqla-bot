music.py

import os
import requests

AUDD_API_URL = "https://api.audd.io/"

def find_song(audio_file):
"""Audio fayldagi qo‘shiqni aniqlashga urinadi."""
api_token = os.getenv("AUDD_API_TOKEN")

if not api_token:
    return {"error": "AUDD_API_TOKEN sozlanmagan"}

try:
    with open(audio_file, "rb") as audio:
        response = requests.post(
            AUDD_API_URL,
            data={"api_token": api_token},
            files={"file": audio},
            timeout=30,
        )

    response.raise_for_status()
    return response.json()

except requests.RequestException:
    return {"error": "Musiqani aniqlash xizmati bilan aloqa bo‘lmadi"}