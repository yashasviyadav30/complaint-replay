"""running_app must leave nothing behind: a leftover server kept workspace/badshop locked and failed 8 tests."""

import urllib.request

from replay.project import running_app

# The shell exits at once and the server lives on as a detached grandchild, the way launchers and dev tools do.
START = ('{python} -c "import subprocess, sys; subprocess.Popen([sys.executable, \'-m\', \'http.server\', \'{port}\', '
         '\'--bind\', \'127.0.0.1\'], creationflags=0x8 if sys.platform == \'win32\' else 0, start_new_session=True)"')


def test_the_app_is_stopped_even_when_its_shell_exited_first(tmp_path) -> None:
    (tmp_path / "complaint-replay.toml").write_text(f'[app]\nstart = """{START}"""\nready = "/"\n', encoding="utf-8")
    with running_app(tmp_path) as url:
        urllib.request.urlopen(url, timeout=5)
    try:
        urllib.request.urlopen(url, timeout=2)
        still_up = True
    except OSError:
        still_up = False
    assert not still_up, f"{url} still answers after running_app closed"
