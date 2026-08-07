import logging
from typing import Optional
try:
    import grpc
except ImportError:
    grpc = None  # type: ignore

logger = logging.getLogger(__name__)

# Map UI language codes to Magpie-Multilingual voices
VOICE_MAP = {
    'en': 'Magpie-Multilingual.EN-US.Aria',
    'hi': 'Magpie-Multilingual.HI-IN.Aria',
    'es': 'Magpie-Multilingual.ES-ES.Aria',
    'fr': 'Magpie-Multilingual.FR-FR.Aria',
    'de': 'Magpie-Multilingual.DE-DE.Aria',
    'it': 'Magpie-Multilingual.IT-IT.Aria',
    'zh': 'Magpie-Multilingual.ZH-CN.Aria',
    'ja': 'Magpie-Multilingual.JA-JP.Aria',
    'vi': 'Magpie-Multilingual.VI-VN.Aria'
}

def create_wav_header(pcm_data: bytes, sample_rate: int = 22050) -> bytes:
    """Wraps raw PCM bytes in a WAV container (16-bit Mono)."""
    import struct
    num_channels = 1
    sample_width = 2
    header = b'RIFF'
    header += struct.pack('<I', 36 + len(pcm_data))
    header += b'WAVEfmt '
    header += struct.pack('<I', 16)
    header += struct.pack('<H', 1) 
    header += struct.pack('<H', num_channels)
    header += struct.pack('<I', sample_rate)
    header += struct.pack('<I', sample_rate * num_channels * sample_width)
    header += struct.pack('<H', num_channels * sample_width)
    header += struct.pack('<H', sample_width * 8)
    header += b'data'
    header += struct.pack('<I', len(pcm_data))
    return header + pcm_data

def synthesize_speech(text: str, language: str = 'en') -> Optional[bytes]:
    """
    Sends clinical summary to NVIDIA Magpie Multilingual model via direct gRPC.
    """
    SERVER = "grpc.nvcf.nvidia.com:443"
    FUNCTION_ID = "877104f7-e885-42b9-8de8-f6e4c6303969"
    AUTH_TOKEN = "Bearer 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"

    try:
        # Lazy import so the module loads fine without the Riva SDK installed
        import grpc as _grpc
        from riva.client.proto import riva_tts_pb2, riva_tts_pb2_grpc
        grpc = _grpc

        # Enforce clinical brevity
        clean_text = text[:1000]
        
        # Resolve voice
        voice_name = VOICE_MAP.get(language, VOICE_MAP['en'])
        lang_code = voice_name.split('.')[1].replace('_','-')
        
        # Prepare gRPC metadata
        metadata = [
            ('function-id', FUNCTION_ID),
            ('authorization', AUTH_TOKEN)
        ]
        
        logger.info(f"Synthesizing Magpie TTS (gRPC Low-Level): [{language}] -> {voice_name}")
        
        # Establish secure channel and stub
        credentials = grpc.ssl_channel_credentials()
        with grpc.secure_channel(SERVER, credentials) as channel:
            stub = riva_tts_pb2_grpc.RivaSynthesizerStub(channel)
            
            # Construct request
            request = riva_tts_pb2.SynthesizeSpeechRequest(
                text=clean_text,
                language_code=lang_code,
                encoding=1, # LINEAR_PCM
                sample_rate_hz=22050,
                voice_name=voice_name
            )
            
            # Call Synthesize (Unary)
            response = stub.Synthesize(request, metadata=metadata)
            
            if not response.audio:
                raise ValueError("No audio content returned from Magpie worker")
                
            return create_wav_header(response.audio, 22050)

    except Exception as e:
        logger.error(f"Magpie TTS Low-Level Error: {e}")
        raise ValueError(f"Synthesis failed: {str(e)}")

def transcribe_audio(file_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    NVIDIA Whisper NIM STT (REST fallback for ease of binary upload).
    """
    import requests
    STT_ENDPOINT = "https://integrate.api.nvidia.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    files = {"file": (filename, file_bytes, "audio/webm")}
    data = {"model": "openai/whisper-large-v3", "response_format": "text"}
    
    try:
        response = requests.post(STT_ENDPOINT, headers=headers, files=files, data=data, timeout=12)
        response.raise_for_status()
        return response.json().get("text", "") if "application/json" in response.headers.get("Content-Type", "") else response.text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""

