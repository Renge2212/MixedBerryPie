#!/usr/bin/env python3
import os
import re
import subprocess
import sys


def refine_xml_format(path: str) -> None:
    """Refine the .ts XML format to be human-readable and standard."""
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as f:
        content = f.read()

    # 1. Collapse all whitespace between tags
    content = re.sub(r">\s+<", "><", content)

    # 2. Define structure
    containers = ["TS", "context", "message"]

    lines = []
    indent = 0
    parts = re.split(r"(<[^>]+>)", content)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if part.startswith("</"):
            tag_match = re.match(r"</([^> ]+)>", part)
            tag_name = tag_match.group(1) if tag_match else ""
            if tag_name in containers:
                indent -= 1
                lines.append("    " * indent + part)
            else:
                if lines:
                    lines[-1] = lines[-1] + part
        elif part.startswith("<") and not part.endswith("/>") and not part.startswith("<?"):
            tag_match = re.match(r"<([^> ]+)", part)
            tag_name = tag_match.group(1) if tag_match else ""
            if tag_name in containers:
                lines.append("    " * indent + part)
                indent += 1
            else:
                lines.append("    " * indent + part)
        elif part.startswith("<"):
            lines.append("    " * indent + part)
        else:
            if lines:
                lines[-1] = lines[-1] + part

    final_content = "\n".join(lines)
    final_content = re.sub(r"<\?xml(.*?)\?><TS", r"<?xml\1?>\n<TS", final_content)

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(final_content)


def main() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ts_file = os.path.join(project_root, "resources", "translations", "piemenu_ja.ts")

    # Locate lupdate
    lupdate_path = os.path.join(project_root, ".venv", "Scripts", "pyside6-lupdate.exe")
    if not os.path.exists(lupdate_path):
        lupdate_path = "pyside6-lupdate"

    print(f"Finding Python files in {project_root}/src...")
    py_files = []
    for root, _, files in os.walk(os.path.join(project_root, "src")):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    if not py_files:
        print("No Python files found.")
        return

    print(f"Running lupdate on {len(py_files)} files...")
    try:
        # Pass all files at once
        cmd = [lupdate_path, *py_files, "-ts", ts_file]
        subprocess.run(cmd, check=True, cwd=project_root)
        print("Successfully updated .ts file from source strings.")
    except Exception as e:
        print(f"Error running lupdate: {e}")
        sys.exit(1)

    print("Refining XML format...")
    refine_xml_format(ts_file)
    print("Done.")


if __name__ == "__main__":
    main()
