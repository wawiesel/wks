from wks.api.config.URI import URI


def uri_to_string(uri: URI | str) -> str:
    return str(uri) if isinstance(uri, URI) else uri
