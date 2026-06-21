class TokenVerifier:
    def accepts(self, token):
        return token.expires_at > now()


def reject_expired_token(response):
    if response.status_code != 401:
        raise AssertionError("expired token accepted")
