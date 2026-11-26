"""Shared, dependency-free quality measurements for the site and checker."""

import re


def parse_colors(css):
    """Return custom-property palettes declared by each theme in site CSS."""
    palettes = {}
    for selector, body in re.findall(r'(:root(?:\[data-theme="[^"]+"\])?)\s*\{([^}]+)\}', css):
        theme = selector or "dark"
        if theme == ":root":
            theme = "dark"
        elif theme.startswith(":root"):
            theme = re.search(r'data-theme="([^"]+)"', theme).group(1)
        palettes.setdefault(theme, dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})", body)))
    return palettes


def _luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear))


def contrast_ratio(first, second):
    values = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (values[0] + 0.05) / (values[1] + 0.05)


def contrast_report(css):
    """Measure real text, muted text, accent, and border pairs for both themes."""
    palettes = parse_colors(css)
    results = {}
    required = {"--background", "--surface", "--text", "--muted", "--accent", "--border", "--tok-key", "--tok-str"}
    for theme in ("dark", "light"):
        palette = palettes.get(theme, {})
        missing = required - palette.keys()
        if missing:
            return False, {theme: {"error": "missing " + ", ".join(sorted(missing))}}
        background = palette["--background"]
        ratios = {
            "text": contrast_ratio(palette["--text"], background),
            "muted": contrast_ratio(palette["--muted"], background),
            "accent": contrast_ratio(palette["--accent"], background),
            "border": contrast_ratio(palette["--border"], background),
            "menu_link_surface": contrast_ratio(palette["--accent"], palette["--surface"]),
            "menu_label_surface": contrast_ratio(palette["--muted"], palette["--surface"]),
            "menu_hover_background": contrast_ratio(palette["--text"], background),
            "token_key_surface": contrast_ratio(palette["--tok-key"], palette["--surface"]),
            "token_string_surface": contrast_ratio(palette["--tok-str"], palette["--surface"]),
        }
        results[theme] = ratios
    passed = all(
        result["text"] >= 4.5
        and result["muted"] >= 4.5
        and result["accent"] >= 4.5
        and result["border"] >= 3.0
        and result["menu_link_surface"] >= 4.5
        and result["menu_label_surface"] >= 4.5
        and result["menu_hover_background"] >= 4.5
        and result["token_key_surface"] >= 4.5
        and result["token_string_surface"] >= 4.5
        for result in results.values()
    )
    return passed, results
