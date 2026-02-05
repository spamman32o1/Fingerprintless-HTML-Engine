from fingerprintless_html_engine import html_utils


class _FakeLanguage:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeDetector:
    def __init__(self, mapping: dict[str, str | None]) -> None:
        self.mapping = mapping

    def detect_language_of(self, text: str):
        name = self.mapping.get(text.lower())
        if name is None:
            return None
        return _FakeLanguage(name)


def test_extract_lang_prefers_explicit_html_lang() -> None:
    html = '<html lang="fr"><body><p>Hello world</p></body></html>'

    assert html_utils.extract_lang(html) == "fr"


def test_detects_single_language_without_lang_attribute(monkeypatch) -> None:
    detector = _FakeDetector({"bonjour": "FRENCH", "monde": "FRENCH"})
    monkeypatch.setattr(html_utils, "_get_lingua_detector", lambda: detector)

    html = "<html><body><h1>Bonjour monde</h1></body></html>"

    assert html_utils.extract_lang(html) == "fr"


def test_mixed_language_uses_majority_detection(monkeypatch) -> None:
    detector = _FakeDetector(
        {
            "hello": "ENGLISH",
            "world": "ENGLISH",
            "bonjour": "FRENCH",
        }
    )
    monkeypatch.setattr(html_utils, "_get_lingua_detector", lambda: detector)

    html = "<html><body>Hello world bonjour</body></html>"

    assert html_utils.extract_lang(html) == "en"


def test_empty_or_non_text_falls_back_to_english(monkeypatch) -> None:
    detector = _FakeDetector({})
    monkeypatch.setattr(html_utils, "_get_lingua_detector", lambda: detector)

    assert html_utils.extract_lang("<html><body><div><br/></div></body></html>") == "en"
    assert html_utils.extract_lang("<html><body><script>var a = 1;</script></body></html>") == "en"
