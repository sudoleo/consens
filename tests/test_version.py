"""The build id from the checkout (app/core/version.py), in a main checkout and in a worktree."""
from app.core.version import _from_git_dir

SHA = "0123456789abcdef0123456789abcdef01234567"


def _repo(tmp_path, *, packed=False):
    git = tmp_path / "repo" / ".git"
    (git / "refs" / "heads" / "feature").mkdir(parents=True)
    if packed:
        (git / "packed-refs").write_text(f"# pack-refs with: peeled\n{SHA} refs/heads/feature/x\n", encoding="utf-8")
    else:
        (git / "refs" / "heads" / "feature" / "x").write_text(SHA + "\n", encoding="utf-8")
    return git


def test_a_main_checkout_reads_its_branch(tmp_path):
    git = _repo(tmp_path)
    (git / "HEAD").write_text("ref: refs/heads/feature/x\n", encoding="utf-8")
    assert _from_git_dir(tmp_path / "repo") == SHA


def test_a_worktree_on_a_branch_reads_it_from_the_common_directory(tmp_path):
    for packed in (False, True):
        root = tmp_path / ("packed" if packed else "loose")
        git = _repo(root, packed=packed)
        own = git / "worktrees" / "w"
        own.mkdir(parents=True)
        (own / "HEAD").write_text("ref: refs/heads/feature/x\n", encoding="utf-8")
        (own / "commondir").write_text("../..\n", encoding="utf-8")
        tree = root / "w"
        tree.mkdir()
        (tree / ".git").write_text(f"gitdir: {own}\n", encoding="utf-8")
        assert _from_git_dir(tree) == SHA, packed


def test_a_detached_worktree_reads_its_own_head(tmp_path):
    own = tmp_path / "repo" / ".git" / "worktrees" / "w"
    own.mkdir(parents=True)
    (own / "HEAD").write_text(SHA + "\n", encoding="utf-8")
    tree = tmp_path / "w"
    tree.mkdir()
    (tree / ".git").write_text(f"gitdir: {own}\n", encoding="utf-8")
    assert _from_git_dir(tree) == SHA
