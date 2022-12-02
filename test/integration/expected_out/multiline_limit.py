app = _app_ctx_stack.top.app
banner = "Python %s on %s\nApp: %s [%s]\nInstance: %s" % (
    sys.version,
    sys.platform,
    app.import_name,
    app.env,
    app.instance_path,
)
ctx = {}
