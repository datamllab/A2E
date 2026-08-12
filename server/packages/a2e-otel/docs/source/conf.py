"""
Configuration file for the A2E OTEL Sphinx documentation builder.
"""

# -- Path setup --------------------------------------------------------------

import os
import sys

# Path setup for autodoc
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "src", "a2e"))

# -- Project information -----------------------------------------------------

project = "A2E OTEL Reference"
copyright = "2025, Shanghai AI Lab"
author = "Shanghai AI Lab"

# The version info for the project you're documenting
try:
    from a2e.otel import __version__ as version

    release = version
except ImportError:
    version = "latest"
    release = "latest"

# -- General configuration ---------------------------------------------------

source_suffix = [".rst", ".md", ".txt"]

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_design",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files
# and directories to ignore when looking for source files.
exclude_patterns: list[str] = []

add_module_names = False

# -- Extension configuration -------------------------------------------------

# Napoleon
napoleon_google_docstring = True
napoleon_numpy_docstring = True

# Autosummary
autosummary_generate = True

# MyST
myst_enable_extensions = ["colon_fence", "linkify", "substitution"]
myst_heading_anchors = 2

# Autodoc
autoclass_content = "class"
autodoc_typehints = "none"
add_function_parentheses = False
add_module_names = False
autodoc_preserve_defaults = True

autodoc_default_options = {
    "members": True,
    "private-members": False,
    "special-members": "",
    "undoc-members": False,
    "inherited-members": False,
    "show-inheritance": False,
}

# -- Internationalization ----------------------------------------------------

language = "en"

# -- Versioning --------------------------------------------------------------

json_url = "https://a2e-otel.readthedocs.io/en/latest/_static/switcher.json"
version_match = os.environ.get("READTHEDOCS_VERSION")

if not version_match or version_match.isdigit() or version_match == "stable":
    version_match = f"v{release}"

# -- Options for HTML output -------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_show_sphinx = False

html_theme_options = {
    "logo": {
        "text": "A2E OTEL",
        "image_light": "logo.png",
        "image_dark": "logo.png",
    },
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/a2e-ai/a2e",
            "icon": "fa-brands fa-github",
        },
        {
            "name": "X",
            "url": "https://x.com/ArizeA2E",
            "icon": "fa-brands fa-x-twitter",
        },
    ],
    "external_links": [
        {"name": "A2E Docs", "url": "https://example.com/docs/a2e"},
        {"name": "Python Reference", "url": "https://a2e-server.readthedocs.io/"},
    ],
    "navbar_align": "content",
    "navbar_start": ["navbar-logo"],
    "secondary_sidebar_items": [],
    "footer_start": [],
    "footer_end": ["copyright"],
    "navigation_depth": 3,
    "collapse_navigation": True,
}

html_sidebars = {
    "**": ["custom_sidebar.html"],
    "index": [],
}
