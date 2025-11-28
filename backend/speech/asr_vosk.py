# speech/asr_vosk.py

import os
import json
import wave
from vosk import Model, KaldiRecognizer

# -------------------------
# 加载模型（只加载一次）
# -------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "speech", "vosk-model")

print(">>> 加载 Vosk 中文模型中...")
model = Model(MODEL_PATH)
print(">>> Vosk 模型加载完成")


# -------------------------
# 识别 WAV 文件（16kHz / mono）
# -------------------------
def transcribe_audio_file(wav_path: str) -> str:
    """
    从 WAV 文件路径识别语音
    WAV 格式要求：
        - PCM
        - Mono
        - 16000 Hz
        （在 main.py 转换时已经保证）
    """
    wf = wave.open(wav_path, "rb")

    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    text_result = ""

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            text_result += res.get("text", "") + " "

    # Final result
    res = json.loads(rec.FinalResult())
    text_result += res.get("text", "")

    wf.close()

    text_result = text_result.strip()
    return text_result if text_result else "（识别失败）"