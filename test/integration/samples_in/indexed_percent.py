def test_context_binding(app):
    @app.route("/")
    def index():
        return "Hello %s!" % flask.request.args[name]
