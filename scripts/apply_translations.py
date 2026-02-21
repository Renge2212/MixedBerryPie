#!/usr/bin/env python3
# ruff: noqa: S314
"""
Apply Japanese translations to piemenu_ja.xml file.
This script replaces all unfinished translations with Japanese equivalents.
"""

import os
import xml.etree.ElementTree as ET

# Translation mapping: English -> Japanese
TRANSLATIONS = {
    # HelpDialog
    "Pie Menu Help": "Pie Menu ヘルプ",
    "Close": "閉じる",
    "Not Set": "未設定",
    "How to Use": "使い方",
    "Press the trigger key:": "トリガーキーを押す:",
    "The pie menu appears centered on your mouse cursor": "マウスカーソルの中心にパイメニューが表示されます",
    "Move your mouse to select an item (highlighted)": "マウスを動かしてアイテムを選択（ハイライト表示）",
    "Release the trigger key to execute the selected action": "トリガーキーを離すと選択したアクションが実行されます",
    "Release without selection to send the original key": "何も選択せずに離すと元のキーが送信されます",
    "Configured Shortcuts": "設定済みショートカット",
    "Displaying Default Profile": "デフォルトプロファイルを表示中",
    "Label": "ラベル",
    "Action": "アクション",
    "Color": "色",
    "Settings": "設定",
    "Trigger Key:": "トリガーキー:",
    "Action Delay:": "アクション遅延:",
    "Overlay Size:": "オーバーレイサイズ:",
    "Tips": "ヒント",
    "Right-click the system tray icon to access settings": "設定にアクセスするにはシステムトレイアイコンを右クリックしてください",
    "Customize colors, labels, and shortcuts in the settings window": "設定ウィンドウで色、ラベル、ショートカットをカスタマイズできます",
    "Pie Menu works in any application": "パイメニューはどのアプリケーションでも動作します",
    "Logs are saved to": "ログの保存先:",
    "for troubleshooting": "（トラブルシューティング用）",
    "Troubleshooting": "トラブルシューティング",
    "If actions don't execute, try increasing the Action Delay in settings": "アクションが実行されない場合は、設定でアクション遅延を増やしてみてください",
    "If the trigger key doesn't work, check for conflicts with other apps": "トリガーキーが機能しない場合は、他のアプリとの競合を確認してください",
    "Check the log file for detailed error messages": "詳細なエラーメッセージについてはログファイルを確認してください",
    # IconPickerWidget
    "Select Icon": "アイコンを選択",
    "Search icons...": "アイコンを検索...",
    "No Icon": "アイコンなし",
    # ItemEditorDialog
    "Edit Item": "アイテムを編集",
    "Label:": "ラベル:",
    "Key:": "キー:",
    "Color:": "色:",
    "Icon:": "アイコン:",
    "Action Type:": "アクションタイプ:",
    "Send Key": "キーを送信",
    "Open URL": "URLを開く",
    "Run Command": "コマンドを実行",
    "URL:": "URL:",
    "Command:": "コマンド:",
    "https://example.com": "https://example.com",
    "notepad.exe or C:\\Path\\To\\App.exe": "notepad.exe または C:\\Path\\To\\App.exe",
    "Images (*.png *.jpg *.jpeg *.ico *.svg);;All Files (*)": "画像ファイル (*.png *.jpg *.jpeg *.ico *.svg);;すべてのファイル (*)",
    "OK": "OK",
    "Cancel": "キャンセル",
    "Error": "エラー",
    "Label cannot be empty": "ラベルを入力してください",
    "Key cannot be empty": "キーを入力してください",
    "URL cannot be empty": "URLを入力してください",
    "Command cannot be empty": "コマンドを入力してください",
    "Key Conflict": "キーの競合",
    "The key '{key}' is already used by the trigger key. Please choose a different key.": "キー '{key}' はトリガーキーとして使用されています。別のキーを選択してください。",
    # SettingsWindow
    "Pie Menu Settings": "パイメニュー設定",
    "Profiles": "プロファイル",
    "Add Profile": "プロファイルを追加",
    "Remove Profile": "プロファイルを削除",
    "Rename Profile": "プロファイル名を変更",
    "Profile Name:": "プロファイル名:",
    "Click to set": "クリックして設定",
    "Active Applications:": "有効なアプリケーション:",
    "Global (empty) or 'chrome.exe', 'Notepad'...": "グローバル（空欄）または 'chrome.exe', 'Notepad'...",
    "Comma-separated list of executable names or window titles.\nEmpty means enabled for all applications.": "実行ファイル名またはウィンドウタイトルをカンマ区切りで指定。\n空欄の場合はすべてのアプリケーションで有効になります。",
    "Add Item": "項目を追加",
    "Remove Item": "項目を削除",
    "Move Up": "上へ移動",
    "Move Down": "下へ移動",
    "General Settings": "一般設定",
    "Action Delay (ms):": "アクション遅延 (ms):",
    "Overlay Size (px):": "オーバーレイサイズ (px):",
    "Icon Size (px):": "アイコンサイズ (px):",
    "Start with Windows": "Windows起動時に開始",
    "Language:": "言語:",
    "Auto (System Default)": "自動（システムデフォルト）",
    "English": "English",
    "Japanese": "日本語",
    "Save": "保存",
    "Confirm Delete": "削除の確認",
    "Are you sure you want to delete the profile '{name}'?": "プロファイル '{name}' を削除してもよろしいですか？",
    "Cannot Delete": "削除できません",
    "Cannot delete the last profile.": "最後のプロファイルは削除できません。",
    "New Profile Name": "新しいプロファイル名",
    "Enter new profile name:": "新しいプロファイル名を入力:",
    "Profile '{new_name}' already exists.": "プロファイル '{new_name}' は既に存在します。",
    # WelcomeDialog
    "Welcome to Pie Menu!": "Pie Menu へようこそ！",
    "Pie Menu is a radial menu that appears when you press a trigger key.": "パイメニューは、トリガーキーを押すと表示される放射状メニューです。",
    "Quick Start Guide": "クイックスタートガイド",
    "1. Press the trigger key (default: Middle Mouse Button)": "1. トリガーキーを押す（デフォルト: マウス中ボタン）",
    "2. Move your mouse to select an action": "2. マウスを動かしてアクションを選択",
    "3. Release the key to execute": "3. キーを離して実行",
    "You can customize everything in the settings!": "設定ですべてカスタマイズできます！",
    "Right-click the tray icon to open settings": "トレイアイコンを右クリックして設定を開く",
    "Don't show this again": "次回から表示しない",
    "Get Started": "始める",
    # SystemTray
    "Pie Menu": "パイメニュー",
    "Help": "ヘルプ",
    "Exit": "終了",
    "Exit MixedBerryPie": "MixedBerryPie を終了",
    "MixedBerryPie Help": "MixedBerryPie ヘルプ",
    # Additional translations for missing strings
    "Search:": "検索:",
    "{} icons loaded": "{}個のアイコンを読み込みました",
    "{} icons visible": "{}個のアイコンを表示中",
    "Presets": "プリセット",
    "Value:": "値:",
    "Preview": "プレビュー",
    "Sample": "サンプル",
    "Press key to record...": "キーを押して記録...",
    "Select Color": "色を選択",
    "Input Error": "入力エラー",
    "Please enter a label.": "ラベルを入力してください。",
    "Please set a value.": "値を設定してください。",
    "Cannot set the same key as the global trigger key.": "グローバルトリガーキーと同じキーは設定できません。",
    "Exit PieMenu": "PieMenuを終了",
    "No Items": "アイテムなし",
    "Menu Profiles": "メニュープロファイル",
    "Add": "追加",
    "Delete": "削除",
    "Delete Profile": "プロファイルを削除",
    "Menu Items": "メニュー項目",
    "Global Settings": "グローバル設定",
    "Trigger Key": "トリガーキー",
    "Global Hotkey:": "グローバルホットキー:",
    "Target Apps:": "対象アプリ:",
    "Pick from running apps": "実行中のアプリから選択",
    "Select App": "アプリを選択",
    "Window Title": "ウィンドウタイトル",
    "Process": "プロセス",
    "Select an application from the running windows to add it to target apps.": "実行中のウィンドウからアプリケーションを選択して、対象アプリに追加します。",
    "Refresh": "更新",
    "Add Selected": "選択したアプリを追加",
    "Selection Required": "選択が必要です",
    "Please select an application from the list.": "リストからアプリケーションを選択してください。",
    "Edit": "編集",
    "Remove": "削除",
    "Live Preview": "ライブプレビュー",
    "Icon Size:": "アイコンサイズ:",
    "Trigger Behavior": "トリガー動作",
    "Replay original key if selection cancelled": "選択がキャンセルされた場合は元のキーを再生",
    "If enabled, releasing the trigger key without selecting an item will simulate the original key press.": "有効にすると、アイテムを選択せずにトリガーキーを離した場合、元のキー押下がシミュレートされます。",
    "Long Press Delay:": "長押し遅延:",
    "Delay in milliseconds before showing the menu. 0 means instant.": "メニューを表示するまでの遅延時間（ミリ秒）。0は即座に表示します。",
    "Backup & Restore": "バックアップと復元",
    "Export Settings": "設定をエクスポート",
    "Import Settings": "設定をインポート",
    "Save & Apply": "保存して適用",
    "New Name:": "新しい名前:",
    "Boost your productivity with a modern, fast, and customizable radial menu.": "モダンで高速、カスタマイズ可能な放射状メニューで生産性を向上させましょう。",
    "Press & Hold": "押し続ける",
    "Hold your trigger key (Default: Ctrl+Space)": "トリガーキーを押し続けます（デフォルト: Ctrl+Space）",
    "Move Mouse": "マウスを動かす",
    "Move cursor towards the action you want": "実行したいアクションに向かってカーソルを動かします",
    "Release": "離す",
    "Release the key to execute!": "キーを離して実行！",
    "You can access Settings from the System Tray icon.": "システムトレイアイコンから設定にアクセスできます。",
    "Press Trigger Key:": "トリガーキーを押す:",
    "Pie menu will appear around the mouse cursor position": "マウスカーソルの周りにパイメニューが表示されます",
    "Move mouse to select an item (highlighted)": "マウスを動かしてアイテムを選択 (ハイライト)",
    "Release without selection to replay original key (depending on settings)": "選択せずに離すと元のキー入力を再現します (設定による)",
    "Showing default profile": "デフォルトプロファイルを表示中",
    "Current Settings": "現在の設定",
    "Menu Size:": "メニューサイズ:",
    "Right-click tray icon to open settings": "トレイアイコンを右クリックして設定を開く",
    "Customize colors, labels, and shortcuts in settings": "設定画面で色、ラベル、ショートカットをカスタマイズ",
    "MixedBerryPie works in all applications": "MixedBerryPieはすべてのアプリケーションで動作します",
    "Log file location:": "ログファイルの場所:",
    "(For troubleshooting)": "(トラブルシューティング用)",
    "If actions don't execute, try increasing the action delay in settings": "アクションが実行されない場合は、設定でアクション遅延を増やしてください",
    "If trigger key doesn't respond, check for conflicts with other apps": "トリガーキーが反応しない場合は、他のアプリとの競合を確認してください",
    "Check the log file for detailed errors": "詳細なエラーはログファイルを確認してください",
    "Loading icons...": "アイコンを読み込み中...",
    "Loaded {} icons...": "{}個のアイコンを読み込みました...",
    "e.g. Copy, Paste, Brush...": "例: コピー、貼り付け、ブラシ...",
    "Click to record keys...": "クリックしてキーを記録...",
    "Image Files (*.png *.jpg *.jpeg *.ico *.svg);;All Files (*)": "画像ファイル (*.png *.jpg *.jpeg *.ico *.svg);;すべてのファイル (*)",
    "Enter text...": "テキストを入力...",
    "Press keys...": "キーを押す...",
    "Click to record keys": "クリックしてキーを記録",
    "MixedBerryPie Settings": "MixedBerryPie 設定",
    "All apps (blank) or 'chrome.exe', 'Notepad' etc.": "すべてのアプリ(空白)または 'chrome.exe', 'Notepad' など",
    "Comma-separated list of executables or window titles.\nIf blank, it will be enabled in all apps.": "実行ファイル名またはウィンドウタイトルのカンマ区切りリスト。\n空白の場合、すべてのアプリで有効になります。",
    "Language": "言語",
    "Display": "表示",
    "Menu Opacity:": "メニューの不透明度:",
    "Auto Scale:": "自動スケール:",
    "Automatically adjust icons and text to menu size": "アイコンとテキストをメニューサイズに自動調整する",
    "Text Size:": "テキストサイズ:",
    "Behavior": "動作",
    "Animations:": "アニメーション:",
    "Enable menu open/close animations": "メニューの開閉アニメーションを有効にする",
    "Execution Delay (ms):": "実行遅延 (ミリ秒):",
    "Key Input Interval (ms):": "キー入力間隔 (ミリ秒):",
    "Replay original key on cancel": "キャンセル時に元のキーを再現",
    "If enabled, releasing the trigger key without selecting an item will replay the original key input.": "有効にすると、アイテムを選択せずにトリガーキーを離した場合、元のキー入力が再現されます。",
    "Wait time before showing the menu (ms). 0 for immediate.": "メニューを表示するまでの待機時間(ミリ秒)。0で即時表示。",
    "New name:": "新しい名前:",
    "Profile '{}' already exists.": "プロファイル '{}' は既に存在します。",
    "Welcome to MixedBerryPie!": "MixedBerryPieへようこそ！",
}


def apply_translations(ts_file):
    """Apply translations to the .xml file."""
    tree = ET.parse(ts_file)
    root = tree.getroot()

    applied_count = 0
    total_unfinished = 0

    for context in root.findall(".//context"):
        for message in context.findall("message"):
            source_elem = message.find("source")
            translation_elem = message.find("translation")

            if source_elem is not None and translation_elem is not None:
                source_text = source_elem.text if source_elem.text else ""

                # Check if translation is unfinished
                if translation_elem.get("type") == "unfinished":
                    total_unfinished += 1

                    # Apply translation if available
                    if source_text in TRANSLATIONS:
                        translation_elem.text = TRANSLATIONS[source_text]
                        # Remove the 'type="unfinished"' attribute
                        del translation_elem.attrib["type"]
                        applied_count += 1
                        print(f"✓ Translated: {source_text[:50]}...")
                    else:
                        print(f"✗ Missing translation for: {source_text}")

    print("\n=== Summary ===")
    print(f"Total unfinished: {total_unfinished}")
    print(f"Applied: {applied_count}")
    print(f"Still missing: {total_unfinished - applied_count}")

    # Write the updated file
    tree.write(ts_file, encoding="utf-8", xml_declaration=True)
    print(f"\nTranslations written to {ts_file}")


if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TS_FILE = os.path.join(PROJECT_ROOT, "resources", "translations", "piemenu_ja.ts")

    if not os.path.exists(TS_FILE):
        print(f"File not found: {TS_FILE}")
        exit(1)

    apply_translations(TS_FILE)
