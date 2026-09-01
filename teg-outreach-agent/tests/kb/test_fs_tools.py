from app.kb import fs_tools


def test_list_dir_root_has_index_and_dirs_first():
    out = fs_tools.list_dir(".")
    assert "INDEX.md" in out
    assert "exhibitors/" in out
    lines = [ln for ln in out.splitlines() if ln.strip()][1:]  # drop the "path/" header
    first_file = next(i for i, ln in enumerate(lines) if not ln.rstrip().endswith("/"))
    assert all(lines[i].rstrip().endswith("/") for i in range(first_file))


def test_read_file_returns_content():
    out = fs_tools.read_file("exhibitors/companies/third_rock_techkno.md")
    assert "Third Rock Techkno" in out


def test_read_file_paginates_large_file():
    head = fs_tools.read_file("INDEX.md")
    assert "truncated at 6144" in head
    tail = fs_tools.read_file("INDEX.md", offset=6144)
    assert tail and tail != head


def test_grep_finds_company_profile():
    out = fs_tools.grep("Third Rock Techkno", "exhibitors/companies")
    assert "third_rock_techkno.md:" in out


def test_grep_caps_matches():
    out = fs_tools.grep("the", ".")
    assert "more matches not shown" in out
    assert len([ln for ln in out.splitlines() if ":" in ln]) <= 31


def test_grep_invalid_regex_returns_error_string():
    out = fs_tools.grep("(", ".")
    assert "error" in out.lower()


def test_path_escape_is_refused():
    for call in (
        lambda: fs_tools.read_file("../../../etc/passwd"),
        lambda: fs_tools.list_dir("/"),
        lambda: fs_tools.read_file("exhibitors/../../secrets.txt"),
    ):
        out = call()
        assert "error" in out.lower()
        assert "root:" not in out  # nothing from /etc/passwd leaked


def test_dispatch_routes_and_catches():
    assert "INDEX.md" in fs_tools.dispatch("list_dir", {"path": "."})
    assert "error" in fs_tools.dispatch("read_file", {"path": "nope.md"}).lower()
    assert "error" in fs_tools.dispatch("bogus_tool", {}).lower()
