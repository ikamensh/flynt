@pytest.fixture
def site_packages(modules_tmpdir, monkeypatch):
    """Create a fake site-packages."""
    rv = (
        modules_tmpdir.mkdir("lib")
        .mkdir("python{x[0]}.{x[1]}".format(x=sys.version_info))
        .mkdir("site-packages")
    )
    monkeypatch.syspath_prepend(str(rv))
    return rv
