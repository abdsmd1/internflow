from uuid import uuid4

import pytest

from internflow_api.application.interns import RegisterIntern, RegisterInternCommand
from internflow_api.application.users import (
    Authenticate,
    CreateUserAccount,
    RegisterUser,
    RegisterUserCommand,
)
from internflow_api.domain.exceptions import (
    AccountAlreadyLinkedError,
    EmailAlreadyUsedError,
    InternNotFoundError,
    InvalidCredentialsError,
    InvalidValueError,
    PermissionDeniedError,
    SupervisorNotFoundError,
    WeakPasswordError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.user import Principal, Role, UserId
from internflow_api.domain.value_objects import Email, StudyLevel
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from internflow_api.infrastructure.security.jwt_tokens import JwtTokenService
from tests.factories import HR, TEST_JWT_SECRET, TEST_PASSWORD, FakeClock


@pytest.fixture
def register(
    uow: InMemoryUnitOfWork, clock: FakeClock, hasher: Argon2PasswordHasher
) -> RegisterUser:
    return RegisterUser(uow, clock, hasher)


@pytest.fixture
def tokens(clock: FakeClock) -> JwtTokenService:
    return JwtTokenService(secret=TEST_JWT_SECRET, clock=clock)


def an_intern(uow: InMemoryUnitOfWork, clock: FakeClock) -> InternId:
    return (
        RegisterIntern(uow, clock)
        .execute(
            HR,
            RegisterInternCommand(
                "Sara", "El Amrani", "sara@example.com", "ENSA", StudyLevel.LICENCE
            ),
        )
        .id
    )


class TestRegisterUser:
    def test_password_is_hashed_never_stored_in_clear(
        self, register: RegisterUser, hasher: Argon2PasswordHasher
    ) -> None:
        user = register.execute(RegisterUserCommand("rh@example.com", TEST_PASSWORD, Role.HR))

        assert TEST_PASSWORD not in user.password_hash
        assert user.password_hash.startswith("$argon2id$")
        assert hasher.verify(user.password_hash, TEST_PASSWORD)

    @pytest.mark.parametrize("password", ["trop-court", "x" * 129])
    def test_password_length_policy(self, register: RegisterUser, password: str) -> None:
        with pytest.raises(WeakPasswordError, match="entre 12 et 128"):
            register.execute(RegisterUserCommand("rh@example.com", password, Role.HR))

    def test_password_must_not_contain_email_identifier(self, register: RegisterUser) -> None:
        with pytest.raises(WeakPasswordError, match="identifiant"):
            register.execute(
                RegisterUserCommand("karim.benali@example.com", "karim.benali-2026!", Role.HR)
            )

    def test_short_email_identifier_does_not_ban_every_password(
        self, register: RegisterUser
    ) -> None:
        register.execute(RegisterUserCommand("s@example.com", TEST_PASSWORD, Role.HR))

    def test_email_must_be_unique(self, register: RegisterUser) -> None:
        register.execute(RegisterUserCommand("rh@example.com", TEST_PASSWORD, Role.HR))
        with pytest.raises(EmailAlreadyUsedError):
            register.execute(RegisterUserCommand("RH@example.com", TEST_PASSWORD, Role.HR))

    def test_linked_profile_must_exist(self, register: RegisterUser) -> None:
        with pytest.raises(InternNotFoundError):
            register.execute(
                RegisterUserCommand(
                    "s@example.com", TEST_PASSWORD, Role.INTERN, intern_id=InternId(uuid4())
                )
            )
        with pytest.raises(SupervisorNotFoundError):
            register.execute(
                RegisterUserCommand(
                    "e@example.com",
                    TEST_PASSWORD,
                    Role.SUPERVISOR,
                    supervisor_id=SupervisorId(uuid4()),
                )
            )

    def test_a_profile_has_at_most_one_account(
        self, register: RegisterUser, uow: InMemoryUnitOfWork, clock: FakeClock
    ) -> None:
        intern_id = an_intern(uow, clock)
        register.execute(
            RegisterUserCommand("s1@example.com", TEST_PASSWORD, Role.INTERN, intern_id=intern_id)
        )
        with pytest.raises(AccountAlreadyLinkedError):
            register.execute(
                RegisterUserCommand(
                    "s2@example.com", TEST_PASSWORD, Role.INTERN, intern_id=intern_id
                )
            )

    def test_role_and_profile_must_match(self, register: RegisterUser) -> None:
        with pytest.raises(InvalidValueError, match="Profil incohérent"):
            register.execute(RegisterUserCommand("s@example.com", TEST_PASSWORD, Role.INTERN))


class TestCreateUserAccount:
    def test_only_hr_can_create_accounts(self, register: RegisterUser) -> None:
        supervisor = Principal(
            UserId(uuid4()), Role.SUPERVISOR, supervisor_id=SupervisorId(uuid4())
        )
        with pytest.raises(PermissionDeniedError):
            CreateUserAccount(register).execute(
                supervisor, RegisterUserCommand("x@example.com", TEST_PASSWORD, Role.HR)
            )

    def test_hr_creates_an_account(self, register: RegisterUser) -> None:
        user = CreateUserAccount(register).execute(
            HR, RegisterUserCommand("nouveau.rh@example.com", TEST_PASSWORD, Role.HR)
        )
        assert user.role is Role.HR


class TestAuthenticate:
    @pytest.fixture
    def authenticate(
        self,
        register: RegisterUser,
        uow: InMemoryUnitOfWork,
        hasher: Argon2PasswordHasher,
        tokens: JwtTokenService,
    ) -> Authenticate:
        register.execute(RegisterUserCommand("rh@example.com", TEST_PASSWORD, Role.HR))
        return Authenticate(uow, hasher, tokens)

    def test_valid_credentials_return_a_token_for_the_user(
        self, authenticate: Authenticate, tokens: JwtTokenService
    ) -> None:
        token = authenticate.execute("  RH@Example.com ", TEST_PASSWORD)

        assert tokens.decode(token.value).role is Role.HR
        assert token.expires_in_seconds == 30 * 60

    @pytest.mark.parametrize(
        ("email", "password"),
        [
            ("rh@example.com", "mauvais-mot-de-passe"),
            ("inconnu@example.com", TEST_PASSWORD),
            ("pas-un-email", TEST_PASSWORD),
        ],
    )
    def test_invalid_credentials_share_one_generic_error(
        self, authenticate: Authenticate, email: str, password: str
    ) -> None:
        with pytest.raises(InvalidCredentialsError, match="E-mail ou mot de passe incorrect"):
            authenticate.execute(email, password)

    def test_disabled_account_cannot_log_in(
        self, authenticate: Authenticate, uow: InMemoryUnitOfWork
    ) -> None:
        with uow:
            user = uow.users.get_by_email(Email("rh@example.com"))
            assert user is not None
            user.is_active = False
            uow.users.add(user)
            uow.commit()

        with pytest.raises(InvalidCredentialsError):
            authenticate.execute("rh@example.com", TEST_PASSWORD)
