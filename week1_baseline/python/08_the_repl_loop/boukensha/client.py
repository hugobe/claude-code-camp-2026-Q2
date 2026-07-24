import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from http.client import HTTPException

from .errors import ApiError


class Client:
    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
    TRANSIENT_ERRORS = (
        EOFError,
        ConnectionResetError,
        ConnectionRefusedError,
        socket.timeout,
        socket.gaierror,
        ssl.SSLError,
        HTTPException,
        urllib.error.URLError,
        TimeoutError,
    )
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def __init__(self, builder):
        self.builder = builder

    def call(self, max_output_tokens=1024, tools=None):
        body = json.dumps(
            self.builder.to_api_payload(max_output_tokens=max_output_tokens, tools=tools)
        ).encode("utf-8")


        attempts = 0
        while True:
            attempts += 1
            request = urllib.request.Request(
                self.builder.url, data=body, headers=self.builder.headers, method="POST"
            )
            try:
                with urllib.request.urlopen(request) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as e:
                response_body = e.read().decode("utf-8", errors="replace")
                if e.code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue
                if e.code == 401:
                    raise ApiError("authentication failed (401) — check your API key")
                plural = "" if attempts == 1 else "s"
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({e.code}): {response_body}"
                )
            except self.TRANSIENT_ERRORS as e:
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    )
                time.sleep(self._retry_delay(attempts))

    def _retry_delay(self, attempt):
        return self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
