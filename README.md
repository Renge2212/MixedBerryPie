# MixedBerryPie

キーボードショートカットを素早く呼び出し、生産性を向上させるための、高パフォーマンスでカスタマイズ可能なWindows用ラジアルパイメニューです。

## 機能概要

- **多彩なアクション**: キーボード入力、URL起動、コマンド実行に対応。
- **コンテキスト認識**: アクティブなアプリに応じて自動でプロファイルを切り替え可能。
- **直感的なカスタマイズ**: GUIから色、アイコン、透明度などを視覚的に設定。
- **軽量・高速動作**: リソース消費を最小限に抑え、ゼロレイテンシーでメニューを展開。

## 使い方

### 導入方法
1. [Releases](../../releases) ページから最新のインストーラー (`MixedBerryPie-*-Setup.exe`) をダウンロードしてインストールします。
2. アプリケーションを起動すると、システムトレイにアイコンが常駐します。

### 基本操作
- **メニューの起動**: `Ctrl + Space`（デフォルト設定の場合）
- **アクションの選択**: マウスを目的の項目（スライス）へ移動し、メニュー起動で押したキーを離します。
- **キャンセル**: どの項目も選択されていない状態のままキーを離すか、`Esc` を押します。

### 設定のカスタマイズ
システムトレイの **MixedBerryPie** アイコンを右クリックし、「設定 (Settings)」を選択します。
直感的なウインドウ画面で、メニュー起動ホットキーの変更、各項目の追加・編集、プロファイルの管理などを行えます。

---

##  開発者向け (Development)

ソースコードから実行・ビルドなどを行うための手順です。

### 前提条件
- Windows OS
- [Python 3.12 以上](https://www.python.org/downloads/)
- [uv](https://github.com/astral-sh/uv) (推奨パッケージマネージャー)

### セットアップ・実行方法
1. リポジトリをクローンし、依存関係を構築します:
   ```bash
   git clone https://github.com/Renge2212/MixedBerryPie.git
   cd MixedBerryPie
   uv sync
   ```
2. アプリケーションを実行します:
   ```bash
   uv run run.py
   ```

### テストの実行
```powershell
./run_tests.ps1
```

### ビルドとインストーラーの作成
実行ファイルのビルドを行うには、以下のコマンドを使います:
```bash
uv run python scripts/build.py
```

実行ファイルのビルドからインストーラー作成（Inno Setup 6 必須）までを一括で行うには、以下のPowerShellスクリプトを使用します:
```powershell
./scripts/make_release.ps1
```

> **Note**: PowerShellでエラーが出る（「このシステムではスクリプトの実行が無効になっているため…」）場合は、以下のコマンドで一時的に実行を許可してください：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
> ```

## クレジット (Credits)

- **Icons**: [Lucide Icons](https://lucide.dev/) (ISC License)
- **Framework**: [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) (GPL v3)
- **Input Handling**: [pynput](https://github.com/moses-palmer/pynput) (LGPL)

詳細は [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) をご覧ください。

## ライセンス

- **ソースコード**: [MIT ライセンス](LICENSE) の下で公開されています。
- **配布物 (EXE等)**: 本プロジェクトが依存する [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) が GNU GPL v3 であるため、ビルド済みのバイナリやインストーラーには **GNU GPL v3** が適用されます。

詳細は [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) をご覧ください。
