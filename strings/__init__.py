from strings.en import strings as en_strings

LANGUAGES = {"en": en_strings}

def get_string(key: str, lang: str = "en") -> str:
    lang_strings = LANGUAGES.get(lang, en_strings)
    return lang_strings.get(key, en_strings.get(key, key))
