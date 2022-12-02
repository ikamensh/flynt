def test_context_binding(app):
    @app.route("/")
    def index():
        return f"Hello {flask.request.args[name]}!"
