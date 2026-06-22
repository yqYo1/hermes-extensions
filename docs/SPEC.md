# git-workflow-enforcer プラグイン要件定義書

## 1. 目的

git-workflowスキルの遵守率を向上させるため、遵守していない操作を検出しブロックするHermesプラグイン。

## 2. 基本概念

- **遵守判定**: ツール呼び出し毎にgit-workflowスキルの遵守状況を判定
- **違反検出時**: 全ツールをブロックし、スキル再読了を促す
- **スキル再読了検知**: `skill_view("git-workflow")`呼び出しでブロック解除

## 3. 基本原則

**明示的にブロックに指定されていないコマンドは全て許可です。**

以下の各セクションに記載されていないコマンドは、ワークツリー内外を問わず許可されます。

## 4. ブロック対象

### 4.1 絶対ブロック（正規表現、ワークツリー内外関係なく）

| パターン | ブロック理由 |
|----------|-------------|
| `git\s+clone` | ghq getを使用すべき |
| `git\s+push\s+(-f\|--force)\s+(origin\s+)?(main\|master\|develop)\b` | デフォルトブランチへのforce push禁止 |

### 4.2 ワークツリー外でのブロック（関数内判定）

| コマンド | ブロック条件 |
|----------|-------------|
| `git init` | 実効ディレクトリがghq管理内、または同一コマンド内でリモート設定あり |
| `git checkout`/`git switch` | デフォルトブランチ以外への切り替え |
| `git branch` | ブランチ作成 |
| `git commit` | 常にブロック |
| `git reset` | 常にブロック |
| `git merge`/`git rebase`/`git cherry-pick` | 常にブロック |
| `nix flake update` | ワークツリー外でブロック | ロックファイル更新（編集操作） |
| `git worktree move` | 常にブロック | ワークツリーは固定 |
| `git submodule` | 常にブロック | 複雑でワークフロー違反のリスク高 |
| `git add`/`git stage` | 常にブロック |
| `git remote add` | 常にブロック |
| `git stash`（保存） | ワークツリー外でブロック |
| `git stash pop`（復元） | ワークツリー外でブロック |
| ファイル操作（echo/catリダイレクト、sed -i、cp、mv、rm、mkdir等） | 常にブロック |

### 4.2a ワークツリー外での許可（git stash関連）

| コマンド | 許可理由 |
|----------|----------|
| `git bisect` | 常に許可 | デバッグ用の読取り専用操作 |
| `nix build`/`run`/`develop` | 常に許可 | 読取り専用に近い |
| `git stash list` | 常に許可 | 読取り専用 |
| `git stash show` | 常に許可 | 読取り専用 |
| `gh repo create` | 常に許可 | リモートリポジトリ作成（ローカル編集なし） |
| `gh pr create` | 常に許可 | PR作成（ローカル編集なし） |
| `gh pr merge` | 常に許可 | リモートでのPRマージ（ワークフロー準拠） |

### 4.3 ワークツリー内でのブロック

| コマンド | ブロック条件 |
|----------|-------------|
| `git checkout`/`git switch` | デフォルトブランチへの切り替え |

### 4.4 ツール別ブロック

| ツール | ブロック条件 |
|--------|-------------|
| `write_file` | パスがワークツリー内でない |
| `patch` | 同上 |
| `execute_code` | 常にブロック（ファイル書き込み可能性） |
| `process` (write/submit) | 常にブロック |

### 4.5 許可される操作（常時）

- `read_file`, `search_files`（ファイル閲覧）
- `web_search`, `web_extract`（情報収集）
- `browser_navigate`, `browser_snapshot`, `browser_get_images`（ブラウザ閲覧）
- `terminal`: `git pull`, `git fetch`, `git status`, `git log`, `git diff`, `git worktree list`, `git worktree prune`
- `terminal`: `ls`, `find`, `grep`, `cat`, `readlink`, `pwd`, `cd`
- `terminal`: `nix fmt`, `nix flake check`（読取り専用）
- `terminal`: `gh pr view`, `gh pr status`
- `skill_view`, `skills_list`

## 5. ワークツリー判定

### 5.1 判定方法

```python
def is_in_worktree(path: str) -> bool:
    """パスがワークツリー内か判定"""
    return "/.worktree/" in path

def is_under_ghq(path: str) -> bool:
    """パスがghq管理下か判定"""
    return path.startswith(str(Path.home() / "ghq"))
```

### 5.2 git initの実効ディレクトリ計算

```python
def get_effective_directory(command: str, cwd: str) -> str:
    """コマンド実行後の実効ディレクトリを取得"""
    # cd命令を解析
    cd_match = re.search(r'(?:^|&&|;)\s*cd\s+([^\s;]+)', command)
    if cd_match:
        target = cd_match.group(1)
        if target.startswith('~'):
            target = str(Path.home()) + target[1:]
        elif not target.startswith('/'):
            target = os.path.join(cwd, target)
        cwd = os.path.normpath(target)
    
    # git initの対象ディレクトリを解析
    init_match = re.search(r'git\s+init(?:\s+([^\s;]+))?', command)
    if init_match and init_match.group(1):
        target_dir = init_match.group(1)
        if target_dir.startswith('~'):
            target_dir = str(Path.home()) + target_dir[1:]
        elif not target_dir.startswith('/'):
            target_dir = os.path.join(cwd, target_dir)
        return os.path.normpath(target_dir)
    
    return cwd
```

## 6. ブロックメッセージ

```
【git-workflow遵守違反】この操作はブロックされました。
[違反内容の具体的な説明]
git-workflowスキルを読んでから再試行してください。
```

## 7. 実装方式

### 7.1 フック

- `pre_tool_call`: ツール呼び出し前に遵守判定を行い、違反時はブロック

### 7.2 非遵守フラグ管理

```python
# セッション単位の非遵守フラグ
_non_compliance_flags: Dict[str, bool] = {}  # session_id -> bool

def set_non_compliance(session_id: str):
    """非遵守フラグをセット"""
    _non_compliance_flags[session_id] = True

def clear_non_compliance(session_id: str):
    """非遵守フラグを削除（スキル読了時）"""
    _non_compliance_flags.pop(session_id, None)

def is_non_compliant(session_id: str) -> bool:
    """非遵守状態か判定"""
    return _non_compliance_flags.get(session_id, False)

def gc_session(session_id: str):
    """セッション終了時にGC"""
    _non_compliance_flags.pop(session_id, None)
```

### 7.3 ブロック状態遷移

```
通常状態（遵守判定継続）
  ↓ 非遵守検出
ブロック状態（非遵守フラグセット、全ツールブロック）
  ↓ skill_view("git-workflow")検知
通常状態（非遵守フラグ削除、遵守判定再開）
```

### 7.4 ブロックロジック

```python
def pre_tool_call(tool_name, arguments, context):
    session_id = context["session_id"]
    
    # 非遵守状態なら全ツールブロック
    if is_non_compliant(session_id):
        # skill_view("git-workflow")は許可（読了検知用）
        if tool_name == "skill_view" and arguments.get("name") == "git-workflow":
            clear_non_compliance(session_id)
            return None  # allow
        
        # それ以外は全てブロック
        return {
            "action": "block",
            "message": "【git-workflow遵守違反】非遵守操作が検出されたため、全ツールがブロックされています。git-workflowスキルを読んでから再試行してください。"
        }
    
    # 遵守判定
    if not is_compliant(tool_name, arguments, context):
        set_non_compliance(session_id)
        return {
            "action": "block",
            "message": "【git-workflow遵守違反】この操作はgit-workflowスキルに違反しています。スキルを読んでから再試行してください。"
        }
    
    return None  # allow
```

## 8. 未確定事項

1. ~~`git checkout -b new-branch`のワークツリー内での扱い~~ → **許可**（決定済み）
2. ~~`git worktree add`の許可条件~~ → **`.worktree/`以下のみ**（決定済み）
3. ~~ブロック時のメッセージ表示方法~~ → **A方式（block messageのみ）**（決定済み）
4. ~~セッション跨ぎの読了フラグ管理方法~~ → **非遵守フラグ（変数ベース、セッションGC）**（決定済み）
5. 偽陽性/偽陰性の許容度
