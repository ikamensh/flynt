from __future__ import print_function

from pallets_sphinx_themes import ProjectLink, get_version

# Project --------------------------------------------------------------

project = "Flask"
copyright = "2010 Pallets Team"
author = "Pallets Team"
release, version = get_version("Flask")

# General --------------------------------------------------------------

master_doc = "index"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.log_cabinet",
    "pallets_sphinx_themes",
]
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "werkzeug": ("http://werkzeug.pocoo.org/docs/", None),
    "click": ("https://click.palletsprojects.com/", None),
    "jinja": ("http://jinja.pocoo.org/docs/", None),
    "itsdangerous": ("https://itsdangerous.palletsprojects.com/", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/", None),
    "wtforms": ("https://wtforms.readthedocs.io/en/stable/", None),
    "blinker": ("https://pythonhosted.org/blinker/", None),
}

# HTML -----------------------------------------------------------------

html_theme = "flask"
html_theme_options = {"index_sidebar_logo": False}
html_context = {
    "project_links": [
        ProjectLink("Donate to Pallets", "https://palletsprojects.com/donate"),
        ProjectLink("Flask Website", "https://palletsprojects.com/p/flask/"),
        ProjectLink("PyPI releases", "https://pypi.org/project/Flask/"),
        ProjectLink("Source Code", "https://github.com/pallets/flask/"),
        ProjectLink("Issue Tracker", "https://github.com/pallets/flask/issues/"),
    ]
}
html_sidebars = {
    "index": ["project.html", "localtoc.html", "versions.html", "searchbox.html"],
    "**": ["localtoc.html", "relations.html", "versions.html", "searchbox.html"],
}
singlehtml_sidebars = {"index": ["project.html", "versions.html", "localtoc.html"]}
html_static_path = ["_static"]
html_favicon = "_static/flask-icon.png"
html_logo = "_static/flask-logo-sidebar.png"
html_title = f"Flask Documentation ({version})"
html_show_sourcelink = False
html_domain_indices = False

# LaTeX ----------------------------------------------------------------
