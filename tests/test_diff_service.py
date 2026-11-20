from app.services.diff_service import build_diff, summarize


def test_identical_text_has_no_change():
    diff = build_diff("我那时候在供销社", "我那时候在供销社")
    assert diff["has_change"] is False
    assert diff["change_count"] == 0
    assert diff["fidelity"] == 100


def test_insertion_is_marked_as_add():
    diff = build_diff("我那时候在供销社，工资三十七块", "我那时候在供销社上班，工资三十七块")
    assert diff["has_change"] is True
    assert diff["added"] == 2
    assert diff["removed"] == 0
    added = [s.text for s in diff["segments"] if s.kind == "add"]
    assert added == ["上班"]


def test_deletion_is_marked_as_del():
    diff = build_diff("我那时候非常高兴", "我那时候高兴")
    assert diff["has_change"] is True
    assert diff["removed"] == 2
    deleted = [s.text for s in diff["segments"] if s.kind == "del"]
    assert deleted == ["非常"]


def test_fidelity_drops_when_more_text_is_rewritten():
    light = build_diff("我那时候在供销社上班，工资三十七块五", "我那时候在供销社上班，工资三十七块五毛")
    heavy = build_diff("我那时候在供销社上班，工资三十七块五", "当年我在供销社做事，月薪三十七块五")
    assert light["fidelity"] > heavy["fidelity"]


def test_summary_reads_like_plain_chinese():
    assert summarize("我那时候在供销社", "我那时候在供销社") == "原话未改动"
    text = summarize("我那时候在供销社，工资三十七块", "我那时候在供销社上班，工资三十七块")
    assert "改动 1 处" in text
    assert "原话保留" in text


def test_spans_mark_where_the_change_sits():
    diff = build_diff("我那时候在供销社，工资三十七块", "我那时候在供销社上班，工资三十七块")
    assert diff["length"] == len("我那时候在供销社上班，工资三十七块")
    assert len(diff["spans"]) == 1
    span = diff["spans"][0]
    assert span["start"] == len("我那时候在供销社")
    assert span["end"] - span["start"] == 2


def test_pure_deletion_gives_zero_width_span():
    diff = build_diff("我那时候非常高兴", "我那时候高兴")
    assert len(diff["spans"]) == 1
    assert diff["spans"][0]["start"] == diff["spans"][0]["end"]


def test_unchanged_text_has_no_spans():
    diff = build_diff("我那时候在供销社", "我那时候在供销社")
    assert diff["spans"] == []
    assert diff["length"] == len("我那时候在供销社")


def test_empty_input_is_safe():
    diff = build_diff("", "")
    assert diff["has_change"] is False
    assert diff["segments"] == []