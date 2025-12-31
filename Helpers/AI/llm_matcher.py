import requests
import json
import os
from typing import Optional

class SemanticMatcher:
    def __init__(self, model: str = 'qwen3-vl:2b-custom'):
        """
        Initialize the SemanticMatcher for local LLM server (OpenAI-compatible endpoint).
        """
        # Model name is kept for compatibility but ignored by single-model servers
        self.model = model
        self.api_url = os.getenv("LLM_API_URL", "http://127.0.0.1:8080/v1/chat/completions")
        self.timeout = int(os.getenv("LLM_TIMEOUT", "30"))

    def is_match(self, desc1: str, desc2: str, league: Optional[str] = None) -> bool:
        """
        Determines if two match descriptions refer to the same football fixture.
        
        Args:
            desc1: First description (e.g., "Manchester United vs Liverpool" or full match string)
            desc2: Second description (matching format to desc1)
            league: Optional league/region information for additional context
            
        Returns:
            True if the LLM confidently believes they are the same match, False otherwise.
        """
        context = ""
        if league:
            context = f"Both matches are in the league/competition: {league}. "

        prompt = (
            f"Are the following two football matches the same fixture?\n"
            f"Match A: {desc1}\n"
            f"Match B: {desc2}\n"
            f"{context}"
            f"Answer with exactly one word: 'Yes' if they are the same match, or 'No' if they are different."
        )
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 10,
            "stop": ["\n", "."]  # Encourage strict single-word response
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            content = data['choices'][0]['message']['content'].strip().lower()
            
            # Robust yes/no detection
            if content.startswith('yes'):
                return True
            elif content.startswith('no'):
                return False
            else:
                # Fallback: check for presence of 'yes' anywhere (in case of extra text)
                return 'yes' in content
                
        except requests.Timeout:
            print(f"  [LLM Error] Timeout when matching '{desc1}' vs '{desc2}'")
            return False
        except requests.ConnectionError:
            print(f"  [LLM Error] Connection failed to LLM server at {self.api_url}")
            return False
        except requests.HTTPError as http_err:
            print(f"  [LLM Error] HTTP error: {http_err} | Response: {response.text if 'response' in locals() else 'N/A'}")
            return False
        except Exception as e:
            print(f"  [LLM Error] Unexpected failure matching '{desc1}' vs '{desc2}': {e}")
            return False