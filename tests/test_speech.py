from pathlib import Path

import pytest

from erp_asistan.speech import transcribe

SAMPLE = Path(__file__).parent.parent / "samples" / "audio" / "teklif-komutu.wav"


@pytest.mark.llm
def test_transcribes_turkish_command():
    text = transcribe(SAMPLE).casefold()

    assert "marmara" in text
    assert "teklif" in text
