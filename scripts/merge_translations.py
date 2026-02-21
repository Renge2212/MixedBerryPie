#!/usr/bin/env python3
"""
Merge translations from a backup .xml file into a newly generated .xml file.
This preserves existing translations while incorporating new source strings.
"""

import os
import sys
import xml.etree.ElementTree as ET


def merge_translations(backup_file, new_file, output_file):
    """
    Merge translations from backup_file into new_file and write to output_file.
    """
    # Parse both files
    try:
        backup_tree = ET.parse(backup_file)  # noqa: S314
        backup_root = backup_tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing backup file {backup_file}: {e}")
        print("Attempting to extract translations manually...")
        # If backup is corrupted, we'll skip it
        backup_root = None

    new_tree = ET.parse(new_file)  # noqa: S314
    new_root = new_tree.getroot()

    if backup_root is None:
        print("Backup file could not be parsed. Using new file as-is.")
        new_tree.write(output_file, encoding="utf-8", xml_declaration=True)
        return

    # Build a dictionary of translations from the backup
    # Key: (context_name, source_text) -> translation_text
    translations = {}

    for context in backup_root.findall(".//context"):
        context_name_elem = context.find("name")
        if context_name_elem is None:
            continue
        context_name = context_name_elem.text.strip() if context_name_elem.text else ""

        for message in context.findall("message"):
            source_elem = message.find("source")
            translation_elem = message.find("translation")

            if source_elem is not None and translation_elem is not None:
                source_text = source_elem.text if source_elem.text else ""
                translation_text = translation_elem.text if translation_elem.text else ""

                # Only store non-empty translations
                if translation_text:
                    key = (context_name, source_text)
                    translations[key] = translation_text

    print(f"Extracted {len(translations)} translations from backup file.")

    # Apply translations to the new file
    applied_count = 0
    for context in new_root.findall(".//context"):
        context_name_elem = context.find("name")
        if context_name_elem is None:
            continue
        context_name = context_name_elem.text.strip() if context_name_elem.text else ""

        for message in context.findall("message"):
            source_elem = message.find("source")
            translation_elem = message.find("translation")

            if source_elem is not None and translation_elem is not None:
                source_text = source_elem.text if source_elem.text else ""
                key = (context_name, source_text)

                if key in translations:
                    # Apply the translation
                    translation_elem.text = translations[key]
                    # Remove the 'type="unfinished"' attribute if present
                    if "type" in translation_elem.attrib:
                        del translation_elem.attrib["type"]
                    applied_count += 1

    print(f"Applied {applied_count} translations to the new file.")

    # Write the merged result
    new_tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"Merged translations written to {output_file}")


if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TRANSLATIONS_DIR = os.path.join(PROJECT_ROOT, "resources", "translations")

    backup_file = os.path.join(TRANSLATIONS_DIR, "piemenu_ja.xml.backup")
    new_file = os.path.join(TRANSLATIONS_DIR, "piemenu_ja.xml")
    output_file = new_file  # Overwrite the new file

    if not os.path.exists(backup_file):
        print(f"Backup file not found: {backup_file}")
        sys.exit(1)

    if not os.path.exists(new_file):
        print(f"New file not found: {new_file}")
        sys.exit(1)

    merge_translations(backup_file, new_file, output_file)
