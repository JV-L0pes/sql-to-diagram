class EmailAlreadyRegisteredError(ValueError):
    def __init__(self, email: str):
        super().__init__(f"Email already registered: {email!r}")


class InvalidCredentialsError(ValueError):
    def __init__(self):
        super().__init__("Invalid email or password")


class InvalidRefreshTokenError(ValueError):
    def __init__(self):
        super().__init__("Invalid or expired refresh token")


class ProjectNotFoundError(ValueError):
    def __init__(self, project_id: str):
        super().__init__(f"Project not found: {project_id!r}")
