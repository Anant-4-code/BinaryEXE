import requests
import json

API_KEY = "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"
FUNCTION_ID = "877104f7-e885-42b9-8de8-f6e4c6303969"
ENDPOINT = f"https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{FUNCTION_ID}"

def test_nvcf_tts_alt():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "audio/wav"
    }
    # Trying NIM-style payload on NVCF endpoint
    data = {
        "input": "This is a clinical report summary for the Sanjeevani platform.",
        "voice": "en-US-1", # Generic voice name
        "model": "nvidia/magpie-tts-multilingual"
    }
    resp = requests.post(ENDPOINT, headers=headers, json=data)
    if resp.status_code == 200:
        print(f"Success! Audio size: {len(resp.content)} bytes")
        with open("test_magpie_v2.wav", "wb") as f:
            f.write(resp.content)
    else:
        # Check if it was a payload error or server error
        print(f"Error ({resp.status_code}): {resp.text}")

if __name__ == "__main__":
    test_nvcf_tts_alt()
