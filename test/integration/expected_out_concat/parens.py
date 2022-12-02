@property
def static_url_path(self):
    """The URL prefix that the static route will be accessible from.

    If it was not configured during init, it is derived from
    :attr:`static_folder`.
    """
    if self._static_url_path is not None:
        return self._static_url_path

    if self.static_folder is not None:
        basename = os.path.basename(self.static_folder)
        return (f"/{basename}").rstrip("/")
