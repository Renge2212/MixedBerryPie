import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS_FILE = os.path.join(PROJECT_ROOT, "resources", "translations", "piemenu_ja.ts")


def fix_ts_file():
    if not os.path.exists(TS_FILE):
        print(f"File not found: {TS_FILE}")
        return

    with open(TS_FILE, encoding="utf-8") as f:
        content = f.read()

    # Fix opening tags with spaces: < tag ... > -> <tag ... >
    # 1. Remove space after <
    content = re.sub(r"<\s+(\w+)", r"<\1", content)
    # 2. Remove space after </ (closing tags)
    content = re.sub(r"<\/\s+(\w+)", r"</\1", content)

    # 3. Remove space before > in simple tags <tag > -> <tag>
    # Capture the tag name and potential attributes, but strip trailing space before >
    content = re.sub(r'(<\/?[\w\s="\'-]+?)\s+>', r"\1>", content)

    # 4. Handle tags with attributes: <tag attr = "val" >
    # Eliminate space around = if desired, but XML parsers usually handle <tag attr="val"> fine.
    # The main issue is < tag >.

    # 5. Fix malformed XML entities: & amp; -> &amp;
    content = re.sub(r"&\s+(amp|lt|gt|quot|apos);", r"&\1;", content)

    # 6. Remove type="vanished" to force usage of these translations
    content = re.sub(r'\s+type="vanished"', "", content)

    # 7. Fix specific string mismatch
    content = content.replace(
        "Hold your trigger key(Default: Ctrl + Space)",
        "Hold your trigger key (Default: Ctrl+Space)",
    )
    content = content.replace(
        "Hold your trigger key (Default: Ctrl + Space)",
        "Hold your trigger key (Default: Ctrl+Space)",
    )
    content = content.replace("（デフォルト: Ctrl + Space）", "（デフォルト: Ctrl+Space）")

    # Now fix content inside <source> and <translation>
    # We want to strip leading/trailing whitespace from the text content ONLY.
    # Pattern: <source> text </source>

    def strip_content(match):
        tag = match.group(1)
        text = match.group(2)
        # return f'<{tag}>{text.strip()}</{tag}>'
        # Be careful not to strip if it carries attributes, but <source> usually doesn't.
        # <translation> has 'type="vanished"' sometimes.
        # So we need to match the opening tag fully.
        return f"<{tag}>{text.strip()}</{tag}>"

    # The regex needs to handle attributes in the opening tag.
    # <source>...</source>
    # <translation type="...">...</translation>

    # Process <source>
    content = re.sub(
        r"<source>(.*?)</source>",
        lambda m: f"<source>{m.group(1).strip()}</source>",
        content,
        flags=re.DOTALL,
    )

    # Process <translation...>...</translation>
    # Capture attributes in group 1, content in group 2
    content = re.sub(
        r"<translation([^>]*)>(.*?)</translation>",
        lambda m: f"<translation{m.group(1)}>{m.group(2).strip()}</translation>",
        content,
        flags=re.DOTALL,
    )

    # Also fix <name> text </name>
    content = re.sub(
        r"<name>(.*?)</name>",
        lambda m: f"<name>{m.group(1).strip()}</name>",
        content,
        flags=re.DOTALL,
    )

    with open(TS_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("Fixed piemenu_ja.xml")


if __name__ == "__main__":
    fix_ts_file()
