from urllib.parse import urlparse


class Url:
    Worldometer_GDP = "https://www.worldometers.info"
    def valid_url(url: str) -> bool:
        try:
            urlparser = urlparse(url)
            return all([urlparser.netloc, urlparser.scheme])
        except:
            return False