import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import kb  # noqa: E402


def test_kb_search_quoted_query_also_matches_its_words(tmp_path):
    root = tmp_path / "knowledge" / "techniques"
    root.mkdir(parents=True)
    head = "---\nkind: technique\ntitle: {t}\ntags: [x]\ndate: 2026-10-10\nagents: [a]\n---\n# {t}\n{b}\n"
    (root / "a.md").write_text(head.format(t="Render states", b="The alpha test of each shader."), encoding="utf-8")
    (root / "b.md").write_text(head.format(t="Grand Theft Auto mods", b="Notes on grand theft auto."), encoding="utf-8")
    (root / "c.md").write_text(head.format(t="Theft", b="A grand plan for auto saves."), encoding="utf-8")
    kroot = tmp_path / "knowledge"
    assert [r["title"] for r in kb.search(kroot, ["alpha test shader"])] == ["Render states"]   # words apart still match
    found = [r["title"] for r in kb.search(kroot, ["grand theft auto"])]
    assert found[0] == "Grand Theft Auto mods" and "Theft" in found                          # the exact phrase ranks first
    assert len(kb.search(kroot, ["shader", "grand"])) == 3                                    # unquoted words: any of them
