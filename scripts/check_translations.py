#!/usr/bin/env python3
import os
import sys

import defusedxml.ElementTree as ElementTree


def check_translations(ts_file: str) -> bool:
    if not os.path.exists(ts_file):
        print(f"Error: {ts_file} not found.")
        return False

    try:
        tree = ElementTree.parse(ts_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing {ts_file}: {e}")
        return False

    unfinished = []
    total = 0

    for context in root.findall(".//context"):
        context_name_elem = context.find("name")
        context_name = (
            context_name_elem.text
            if context_name_elem is not None and context_name_elem.text is not None
            else "Unknown"
        )
        for message in context.findall("message"):
            total += 1
            source_elem = message.find("source")
            source = (
                source_elem.text if source_elem is not None and source_elem.text is not None else ""
            )
            translation = message.find("translation")

            if translation is None:
                continue

            # Check for unfinished attribute or empty translation
            is_unfinished = translation.get("type") == "unfinished"
            is_empty = not translation.text or not translation.text.strip()

            if is_unfinished or is_empty:
                unfinished.append((context_name, source))

    print(f"\nSearching for incomplete translations in: {os.path.basename(ts_file)}")
    print(f"Total entries: {total}")

    if unfinished:
        print(f"Found {len(unfinished)} incomplete translation(s):")
        for ctx, src in unfinished:
            print(f"  [{ctx}] {src[:60]}{'...' if len(src) > 60 else ''}")
        return False
    else:
        print("✓ All translations are complete!")
        return True


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ts_file = os.path.join(project_root, "resources", "translations", "piemenu_ja.ts")

    success = check_translations(ts_file)
    if not success:
        sys.exit(1)
