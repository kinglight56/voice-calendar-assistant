# backend/speech/tts.py
import pyttsx3
import os

def synthesize_text_async(text: str, out_path: str = "tmp/output.mp3"):
    """
    完全离线 TTS，不需要网络、不需要 API Key、不走微软 Edge。
    适合在 Edge-TTS 401 时作为稳定 fallback。
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 185)      # 语速
        engine.setProperty('volume', 1.0)    # 音量

        voices = engine.getProperty('voices')
        # 尝试选择中文女声
        for v in voices:
            if "ZH" in v.id.upper() or "CHINESE" in v.name.upper():
                engine.setProperty('voice', v.id)
                break

        engine.save_to_file(text, out_path)
        engine.runAndWait()
        print(f"[TTS] ✔ 离线语音合成成功: {out_path}")
        return out_path

    except Exception as e:
        print(f"[TTS] ❌ 离线 TTS 失败: {e}")
        return None
