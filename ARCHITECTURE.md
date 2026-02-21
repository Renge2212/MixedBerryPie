# MixedBerryPie — アーキテクチャガイド

> このドキュメントはプロジェクトの構造規約・設計方針・開発ルールを定義します。
> 新機能の追加・リファクタリング時は必ずこのドキュメントを参照してください。

---

## ディレクトリ構造

```
MixedBerryPie/
├── run.py                  # 唯一のエントリポイント（開発・本番共通）
├── pyproject.toml          # プロジェクト設定・依存関係・ツール設定
├── README.md               # ユーザー向け説明
├── ARCHITECTURE.md         # 本ドキュメント（開発者向け）
├── CONTRIBUTING.md         # コントリビューションガイド
├── LICENSE
│
├── src/                    # アプリケーションソースコード（パッケージルート）
│   ├── app.py              # アプリケーション本体（オーケストレーター）
│   ├── core/               # UIに依存しないビジネスロジック
│   │   ├── config.py       # データ構造定義・設定の読み書き
│   │   ├── hook_manager.py # グローバルキーフック管理
│   │   ├── i18n.py         # 国際化（翻訳ファイルのロード）
│   │   ├── logger.py       # ロギング設定
│   │   ├── utils.py        # 汎用ユーティリティ（パス解決等）
│   │   ├── version.py      # バージョン定数
│   │   └── win32_input.py  # Windows APIを用いた低レベル入力シミュレーション
│   └── ui/                 # PyQt6 UIコンポーネント
│       ├── overlay.py      # パイメニューオーバーレイウィジェット
│       ├── settings_ui.py  # 設定ウィンドウ
│       ├── help_dialog.py  # ヘルプダイアログ
│       └── welcome_dialog.py # 初回起動ウェルカムダイアログ
│
├── resources/              # 静的リソース（バイナリ・データ）
│   ├── icons/              # SVGアイコン（Material Design Icons等）
│   └── translations/       # Qt翻訳ファイル（*.ts, *.qm）
│
├── tests/                  # テストスイート
│   ├── conftest.py         # pytest共通フィクスチャ
│   ├── test_app.py
│   ├── test_config.py
│   ├── test_overlay.py
│   └── ...
│
├── scripts/                # 開発・ビルド用スクリプト（アプリ本体ではない）
│   ├── build.py            # PyInstallerビルド
│   ├── make_release.ps1    # リリースパッケージ作成
│   ├── generate_icons.py   # アイコン生成
│   ├── update_translations.py
│   └── ...
│
└── logs/                   # 実行時ログ（.gitignore対象）
```

---

## レイヤー設計

```
┌─────────────────────────────────────┐
│  run.py  (エントリポイント)           │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  src/app.py  (オーケストレーター)     │
│  - QApplication管理                  │
│  - トレイアイコン                     │
│  - コンポーネント間の配線             │
└──────┬──────────────┬───────────────┘
       │              │
┌──────▼──────┐ ┌─────▼──────────────┐
│  src/core/  │ │  src/ui/           │
│  ビジネス   │ │  UIコンポーネント  │
│  ロジック   │ │  (PyQt6 Widget)    │
└─────────────┘ └────────────────────┘
```

### 依存方向のルール

- `core/` は `ui/` に **依存してはならない**
- `ui/` は `core/` に依存してよい
- `app.py` は両方に依存してよい（配線役）
- `scripts/` は `src/` に依存してよいが、逆は禁止

---

## ファイル配置規約

### 新しいUIコンポーネントを追加する場合

→ `src/ui/<component_name>.py` に配置

```python
# 命名規則: PascalCase のクラス名、snake_case のファイル名
# 例: src/ui/color_picker.py → class ColorPickerWidget(QWidget)
```

### 新しいビジネスロジックを追加する場合

→ `src/core/<module_name>.py` に配置

- UIフレームワーク（PyQt6）への依存を持たないこと
- 設定データの読み書きは `config.py` を経由すること

### 新しい設定項目を追加する場合

1. `src/core/config.py` の `AppSettings` または `PieSlice` / `MenuProfile` に追加
2. `src/ui/settings_ui.py` の `_init_settings_tab()` にUIを追加
3. `load_data()` と `_save_internal()` を更新
4. `src/ui/overlay.py` の `_update_dimensions()` または描画メソッドで使用

### 静的リソースを追加する場合

→ `resources/` 以下に配置し、`src/core/utils.py` の `get_resource_path()` でアクセス

```python
# 良い例
path = get_resource_path("resources/icons/my_icon.svg")

# 悪い例（絶対パスのハードコード）
path = "C:/Users/.../icons/my_icon.svg"
```

### スクリプトを追加する場合

→ `scripts/` に配置。アプリ本体の起動には使用しない。

---

## エントリポイント

| ファイル | 用途 |
|---------|------|
| `run.py` | **唯一の正式エントリポイント**。開発時・PyInstaller両対応 |
| `main.py` | 廃止予定（`run.py` と重複）。削除対象 |

> **ルール**: エントリポイントは `run.py` のみ。`src/app.py` の `if __name__ == "__main__":` ブロックは開発デバッグ用として残してよいが、正式起動には使わない。

---

## 設定ファイルの保存場所

| 環境 | パス |
|-----|------|
| 本番（Windows） | `%LOCALAPPDATA%\MixedBerryPie\menu_config.json` |
| 開発（レガシー） | プロジェクトルートの `menu_config.json`（移行後は削除） |

設定ファイルはプロジェクトリポジトリに含めない（`.gitignore` 対象）。

---

## コーディング規約

### Python バージョン

- **Python 3.12+** を前提とする
- 型ヒントは積極的に使用する（`list[str]` 形式、`List[str]` は使わない）

### フォーマット・リント

```bash
# フォーマット
uv run ruff format .

# リント
uv run ruff check .

# 型チェック
uv run mypy src/
```

設定は `pyproject.toml` の `[tool.ruff]` / `[tool.mypy]` セクションに集約。

### 命名規則

| 対象 | 規則 | 例 |
|-----|------|---|
| クラス | PascalCase | `PieOverlay`, `AppSettings` |
| 関数・メソッド | snake_case | `update_selection()` |
| Qt スロット/シグナル | camelCase（Qt 慣習） | `mouseMoveEvent()` |
| 定数 | UPPER_SNAKE_CASE | `CONFIG_FILE`, `APP_NAME` |
| プライベートメソッド | `_` プレフィックス | `_update_dimensions()` |

### UI 文字列

- 多言語対応のために `self.tr()` を使用し、`.ts` ファイル（翻訳ソース）および `.qm` ファイル（バイナリ）を整備済みです。
- 新しいUI文字列を追加した際は、`scripts/update_translations.py` を実行して `.ts` を更新し、`scripts/compile_translations.py` で `.qm` を生成してください。
- 実行時は `src/core/i18n.py` が設定された言語（またはシステムロケール）に基づいて `.qm` をロードします。

---

## テスト規約

```
tests/
├── conftest.py         # 共通フィクスチャ（QApplication等）
├── test_<module>.py    # モジュール単位でテストファイルを作成
```

```bash
# テスト実行
uv run pytest tests/ -v

# または
./run_tests.ps1
```

- UIテストは `QApplication` フィクスチャを `conftest.py` 経由で使用
- `src/core/` のロジックはUIなしでテスト可能にすること

---

## ビルド・リリース

```bash
# 開発起動
uv run run.py

# テスト
uv run pytest

# リント
uv run ruff check .

# PyInstaller ビルド
uv run python scripts/build.py

# リリースパッケージ（Inno Setup 必要）
./scripts/make_release.ps1
```

---

## 既知の技術的負債

| 項目 | 優先度 | 説明 |
|-----|--------|------|
| (現在特になし) | - | 継続的なリファクタリングを推奨 |
