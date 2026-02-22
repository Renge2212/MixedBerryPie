# MixedBerryPie プロジェクト管理ガイド

## 目次

1. [バージョン管理ポリシー](#バージョン管理ポリシー)
2. [ブランチ戦略](#ブランチ戦略)
3. [開発フロー](#開発フロー)
3. [リリース手順](#リリース手順)
4. [ローカルテスト（MSIXインストール）](#ローカルテストmsixインストール)
5. [CI/CD 概要](#cicd-概要)
6. [ディレクトリ構成](#ディレクトリ構成)

---

## バージョン管理ポリシー

**唯一の真実（Single Source of Truth）は `pyproject.toml`** です。

```toml
# pyproject.toml
[project]
version = "1.2.0"  # ← ここだけを手動で変更する
```

- `AppxManifest.xml` と `MixedBerryPie.iss` のバージョンは **ビルド時に自動同期** されます（コミット不要）
- バージョン形式は [Semantic Versioning](https://semver.org/lang/ja/)（`MAJOR.MINOR.PATCH`）

---

## ブランチ戦略（GitHub Flow）

```
main
  ↑ PR マージのみ（直接 push 禁止）
  ├── feature/add-opacity-slider
  ├── fix/menu-crash-on-win11
  └── ...
```

### ブランチ命名規則

| プレフィックス | 用途 | 例 |
|-------------|------|-----|
| `feature/` | 新機能 | `feature/add-opacity-slider` |
| `fix/` | バグ修正 | `fix/menu-crash-on-win11` |
| `docs/` | ドキュメントのみ | `docs/update-readme` |
| `refactor/` | リファクタリング | `refactor/config-module` |
| `ci/` | CI/CD 変更 | `ci/add-msix-build` |

### PR の流れ

```
1. main から feature/xxx ブランチを切る
2. 開発・コミット
3. GitHub で main への PR を作成
4. CI（Lint・型チェック・テスト）が自動実行される
5. レビュー・修正
6. main にマージ → feature/xxx ブランチは削除
```

> [!IMPORTANT]
> `main` への直接 push は禁止です。GitHub の Branch Protection Rules で設定してください。
> （Settings → Branches → main → Require pull request before merging）

---


### 通常の開発

```powershell
# 1. 依存関係をインストール
uv sync --all-extras --dev

# 2. アプリを起動（開発モード）
uv run python run.py

# 3. テスト実行
uv run pytest tests/

# 4. Lint / 型チェック
uv run ruff check .
uv run mypy .

# 5. 翻訳の更新と検証
uv run python scripts/update_translations.py
uv run python scripts/check_translations.py
```

### コミット規約（Conventional Commits）

```
feat:     新機能
fix:      バグ修正
docs:     ドキュメントのみの変更
refactor: リファクタリング
test:     テストの追加・修正
chore:    ビルドやツールの変更
ci:       CI/CD の変更
```

例: `feat(ui): add menu opacity slider`

---

## リリース手順

### 1. バージョンを上げる

```powershell
# pyproject.toml の version を変更
# 例: "1.1.0" → "1.2.0"
```

### 2. コミット & タグ

```powershell
git add pyproject.toml
git commit -m "chore: bump version to 1.2.0"
git tag v1.2.0
git push origin main --tags
```

> [!IMPORTANT]
> タグのバージョンが `pyproject.toml` と一致しない場合、CI が自動的にエラーを出して止まります。

### 3. GitHub Actions が自動実行

タグ push 後、以下が自動で行われます：

| ステップ | 成果物 |
|---------|-------|
| バージョン検証 | タグ ↔ pyproject.toml の整合性チェック |
| EXE ビルド | `dist/MixedBerryPie.exe` |
| Inno Setup | `Output/MixedBerryPie_Setup_v1.2.0.exe` |
| MSIX パッケージ | `dist/MixedBerryPie_v1.2.0.msix`（**署名なし**） |
| GitHub Release | 上記2ファイルを自動添付 |

> [!NOTE]
> タグ名に `-` が含まれる場合（`v1.2.0-beta`）はプレリリース扱いになります。

---

## ローカルテスト（MSIXインストール）

Store に提出する前のローカル動作確認手順です。

### 前提（初回のみ）

```powershell
# 管理者 PowerShell で実行（証明書をトラストストアに追加）
.\scripts\install_cert.ps1
```

### ビルド & 署名 & インストール

```powershell
# 1. EXEをビルド（アプリが起動中の場合は先に終了する）
uv run python scripts/build.py

# 2. MSIXをパッケージ化
.\scripts\package_msix.ps1

# 3. 自己署名証明書で署名（ローカルテスト用）
.\scripts\sign_msix_local.ps1

# 4. dist/MixedBerryPie_v*.msix をダブルクリックしてインストール
```

> [!CAUTION]
> `sign_msix_local.ps1` で生成する証明書はローカルテスト専用です。コミットしないでください（`.gitignore` 対象）。

### アンインストール（PowerShell）

```powershell
Get-AppxPackage -Name "rengedev.MixedBerryPie" | Remove-AppxPackage
```

---

## CI/CD 概要

### CI（`ci.yml`）：mainへのpush / PR時に実行

```
Ruff（Lint） → Mypy（型チェック） → pytest（テスト）
```

### Release（`release.yml`）：`v*` タグ push 時に実行

```
バージョン検証
  → PyInstaller（EXEビルド）
  → Inno Setup（インストーラー）
  → MakeAppx（MSIXパッケージ、署名なし）
  → GitHub Release 作成 & ファイル添付
```

---

## ディレクトリ構成

```
MixedBerryPie/
├── src/
│   ├── core/          # ビジネスロジック（HookManager, Config, i18n）
│   └── ui/            # PyQt6 UI コンポーネント
├── tests/             # pytest テスト
├── resources/         # アイコン、翻訳ファイル等
├── package/
│   ├── AppxManifest.xml   # MSIXマニフェスト（バージョンはビルド時に自動更新）
│   └── assets/            # MSIXアイコン（Square44x44等）
├── scripts/
│   ├── build.py            # PyInstaller ビルド
│   ├── update_version.py   # バージョン同期（CI用）
│   ├── package_msix.ps1    # MSIX パッケージ作成
│   ├── sign_msix_local.ps1 # ローカルテスト用署名
│   ├── install_cert.ps1    # ローカル証明書インストール（初回のみ）
│   ├── update_translations.py # 翻訳の抽出・同期
│   └── check_translations.py  # 翻訳漏れの検証
├── .github/
│   └── workflows/
│       ├── ci.yml          # 継続的インテグレーション
│       └── release.yml     # リリース自動化
├── pyproject.toml     # ★ バージョンの唯一の真実
└── MixedBerryPie.iss  # Inno Setup スクリプト（バージョンはビルド時に自動更新）
```
