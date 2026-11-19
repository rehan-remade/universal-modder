import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import kb  # noqa: E402


def test_kb_search_hits_prefer_lines_with_more_terms(tmp_path):
    root = tmp_path / "knowledge" / "games" / "x"
    root.mkdir(parents=True)
    body = "# Note\nA flat layer list.\nAnother layer here.\nThe layer.\nTrinkets and the layer coexist.\n"
    (root / "a.md").write_text(f"---\nkind: game\ntitle: Note\ngame: X\n---\n{body}", encoding="utf-8")
    hits = kb.search(tmp_path / "knowledge", ["trinkets", "layer"])[0]["hits"]
    assert hits[0] == "Trinkets and the layer coexist."                  # both terms beat earlier one-term lines
    assert hits[1:] == ["A flat layer list.", "Another layer here."]      # then note order
