import jwt


def verify_clawith_jwt(token: str, secret: str, algorithm: str = "HS256") -> str:
    payload = jwt.decode(token, secret, algorithms=[algorithm])
    return payload["sub"]
