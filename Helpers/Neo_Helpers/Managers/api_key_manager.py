# api_key_manager.py
import os
import requests
import json
import base64

# Default fallback URL if env var is missing
DEFAULT_API_URL = "http://127.0.0.1:8080/v1/chat/completions"

def gemini_api_call_with_rotation(prompt_content, generation_config=None, **kwargs):
    """
    Redirects legacy Gemini calls to our local compatible AI server (llama-server/Qwen3-VL).
    """
    api_url = os.getenv("LLM_API_URL", DEFAULT_API_URL)
    # print(f"    [AI Bridge] Sends to: {api_url}")

    # 1. Parse Input (Text + Images)
    prompt_text = ""
    # We need to construct a 'content' list for the OpenAI Vision format
    message_content = []

    if isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                prompt_text += item + "\n"
                message_content.append({"type": "text", "text": item})
            elif isinstance(item, dict) and "inline_data" in item:
                # Extract image data
                b64_data = item["inline_data"].get("data")
                if b64_data:
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_data}"
                        }
                    })
    elif isinstance(prompt_content, str):
        prompt_text = prompt_content
        message_content.append({"type": "text", "text": prompt_content})

    # 2. Parse Config (Temperature)
    temperature = 0.1
    if generation_config:
        if hasattr(generation_config, 'temperature'):
            temperature = generation_config.temperature
        elif isinstance(generation_config, dict) and 'temperature' in generation_config:
            temperature = generation_config['temperature']

    # 3. Construct Payload
    response_format = None
    if generation_config and isinstance(generation_config, dict):
        if generation_config.get("response_mime_type") == "application/json":
            response_format = {"type": "json_object"}

    payload = {
        "messages": [
            {
                "role": "user",
                "content": message_content
            }
        ],
        "temperature": temperature,
        "max_tokens": 4096,
        "stream": False
    }

    if response_format:
        payload["response_format"] = response_format

    try:
        response = requests.post(api_url, json=payload, timeout=180)
        response.raise_for_status()
        
        data = response.json()
        ans = data['choices'][0]['message']['content']

        # 4. Wrap response to match Mock Gemini object interface
        class MockGeminiResponse:
            def __init__(self, content):
                self.text = content
                self.candidates = [
                    type('MockCandidate', (), {
                        'content': type('MockContent', (), {
                            'parts': [type('MockPart', (), {'text': content})]
                        })
                    })
                ]

        return MockGeminiResponse(ans)

    except Exception as e:
        print(f"    [AI Bridge Error] Failed to connect to {api_url}: {e}")
        return None
