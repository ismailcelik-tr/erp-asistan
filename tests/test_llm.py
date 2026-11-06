import json

import httpx

from erp_asistan.llm import OllamaLLM


def _llm(seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": ""}})

    llm = OllamaLLM(model="m")
    llm._http = httpx.Client(transport=httpx.MockTransport(handler))
    return llm


def test_prime_matches_chat_options_and_generates_one_token():
    seen = []
    llm = _llm(seen)

    llm.chat([{"role": "user", "content": "x"}], [])
    llm.prime([{"role": "system", "content": "s"}], [{"type": "function"}])

    chat, prime = seen
    # A different num_ctx would make Ollama reload the model on the first real question.
    assert prime["options"]["num_ctx"] == chat["options"]["num_ctx"]
    assert prime["keep_alive"] == chat["keep_alive"]
    assert prime["options"]["num_predict"] == 1
    assert prime["tools"] == [{"type": "function"}]
