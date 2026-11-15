"""
Gemini LLM service with model fallback, timeout control, and retry logic.
"""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from google import genai
from config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            logger.info("Initializing GenAI client...")
            self._client = genai.Client(api_key=settings.gen_api_key)
        return self._client

    def generate_content(self, prompt: str) -> str:
        """
        Sends prompt to Gemini trying configured models sequentially.
        Includes per-call timeout and rate-limit backoff.
        """
        models = settings.gemini_models
        max_retries = settings.gemini_max_retries_per_model
        timeout = settings.gemini_timeout_seconds

        def _call_api(model_name: str, text: str) -> str:
            response = self.client.models.generate_content(
                model=model_name,
                contents=text,
            )
            return response.text or ""

        for model in models:
            for attempt in range(1, max_retries + 1):
                logger.info("[%s] Attempt %d/%d (timeout: %ds)...", model, attempt, max_retries, timeout)
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(_call_api, model, prompt)
                        result = future.result(timeout=timeout)
                        if result:
                            logger.info("[%s] Successfully generated response (%d chars).", model, len(result))
                            return result

                except TimeoutError:
                    logger.warning("[%s] Request timed out after %ds.", model, timeout)
                except Exception as e:
                    err_msg = str(e)
                    logger.warning("[%s] Attempt %d failed: %s", model, attempt, err_msg)
                    if any(code in err_msg for code in ("429", "503", "high demand")):
                        if attempt < max_retries:
                            backoff = attempt * 5
                            logger.info("Rate limit / server load detected. Waiting %ds...", backoff)
                            time.sleep(backoff)
                            continue
                    # Break out to next model if non-retriable error
                    break

        raise RuntimeError("All Gemini model attempts failed or timed out.")
