import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import auth as auth_router
from app.core.rate_limit import api_uid_limiter, limiter


class AuthSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(auth_router.router)
        cls.client = TestClient(app)

    def setUp(self):
        limiter.reset()
        api_uid_limiter.reset()

    def test_confirm_registration_sets_httponly_session_cookie(self):
        with (
            patch.object(auth_router, "verify_user_token", return_value="owner-1"),
            patch.object(
                auth_router.auth, "get_user",
                return_value=SimpleNamespace(email_verified=True),
            ),
        ):
            response = self.client.post(
                "/confirm-registration", json={"id_token": "firebase-id-token"}
            )
        self.assertEqual(response.status_code, 200)
        cookie = response.headers.get("set-cookie", "").lower()
        self.assertIn("session=firebase-id-token", cookie)
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_confirm_registration_is_rate_limited_per_ip(self):
        statuses = []
        with patch.object(auth_router, "verify_user_token", side_effect=ValueError("bad")):
            for _ in range(31):
                statuses.append(self.client.post(
                    "/confirm-registration", json={"id_token": "bad-token"}
                ).status_code)
        self.assertEqual(statuses[:30], [401] * 30)
        self.assertEqual(statuses[30], 429)

    def test_confirm_registration_notifies_for_recent_google_account(self):
        user = SimpleNamespace(
            email_verified=True,
            user_metadata=SimpleNamespace(creation_timestamp=time.time() * 1000),
            provider_data=[SimpleNamespace(provider_id="google.com")],
        )
        with (
            patch.object(auth_router, "verify_user_token", return_value="google-owner"),
            patch.object(auth_router.auth, "get_user", return_value=user),
            patch.object(
                auth_router,
                "send_new_user_registration_notification",
            ) as notify,
        ):
            response = self.client.post(
                "/confirm-registration", json={"id_token": "firebase-id-token"}
            )

        self.assertEqual(response.status_code, 200)
        notify.assert_called_once_with("google", "google-owner")

    def test_new_email_registration_schedules_telegram_notification(self):
        user = SimpleNamespace(uid="new-owner", email="new@example.test")
        with (
            patch.object(auth_router, "is_password_setup_configured", return_value=True),
            patch.object(
                auth_router, "find_or_provision_user", return_value=(user, True)
            ) as provision,
            patch.object(auth_router, "deliver_password_setup_email") as deliver,
            patch.object(
                auth_router,
                "send_new_user_registration_notification",
            ) as notify,
        ):
            response = self.client.post(
                "/register",
                json={"email": "new@example.test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "check_inbox"})
        provision.assert_called_once_with("new@example.test")
        deliver.assert_called_once_with("new@example.test", setup=True, language="en")
        notify.assert_called_once_with("email/password", "new-owner")

    def test_existing_email_registration_does_not_notify(self):
        with (
            patch.object(auth_router, "is_password_setup_configured", return_value=True),
            patch.object(
                auth_router,
                "find_or_provision_user",
                return_value=(
                    SimpleNamespace(
                        uid="existing-owner",
                        user_metadata=SimpleNamespace(last_sign_in_timestamp=1),
                    ),
                    False,
                ),
            ),
            patch.object(auth_router, "deliver_password_setup_email") as deliver,
            patch.object(
                auth_router,
                "send_new_user_registration_notification",
            ) as notify,
        ):
            response = self.client.post(
                "/register",
                json={"email": "existing@example.test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "check_inbox"})
        deliver.assert_called_once_with("existing@example.test", setup=False, language="en")
        notify.assert_not_called()

    def test_resend_before_first_login_sends_the_setup_mail_again(self):
        never_signed_in = SimpleNamespace(
            uid="pending-owner",
            user_metadata=SimpleNamespace(last_sign_in_timestamp=None),
        )
        with (
            patch.object(auth_router, "is_password_setup_configured", return_value=True),
            patch.object(
                auth_router,
                "find_or_provision_user",
                return_value=(never_signed_in, False),
            ),
            patch.object(auth_router, "deliver_password_setup_email") as deliver,
            patch.object(auth_router, "send_new_user_registration_notification"),
        ):
            self.client.post("/register", json={"email": "pending@example.test"})

        deliver.assert_called_once_with("pending@example.test", setup=True, language="en")

    def test_setup_mails_per_address_are_capped_with_a_neutral_answer(self):
        pending = SimpleNamespace(
            uid="pending-owner",
            user_metadata=SimpleNamespace(last_sign_in_timestamp=None),
        )
        responses = []
        with (
            patch.object(auth_router, "is_password_setup_configured", return_value=True),
            patch.object(
                auth_router, "find_or_provision_user", return_value=(pending, False)
            ) as provision,
            patch.object(auth_router, "deliver_password_setup_email") as deliver,
            patch.object(auth_router, "send_new_user_registration_notification"),
        ):
            for index in range(auth_router._SETUP_MAILS_PER_ADDRESS + 1):
                # Jede Anfrage kommt von einer anderen IP: das IP-Limit greift
                # nicht, die Bremse pro Adresse schon.
                responses.append(
                    self.client.post(
                        "/register",
                        json={"email": "Victim@Example.test"},
                        headers={"CF-Connecting-IP": f"198.51.100.{index + 1}"},
                    )
                )
            other = self.client.post(
                "/register",
                json={"email": "someone-else@example.test"},
                headers={"CF-Connecting-IP": "198.51.100.200"},
            )

        self.assertEqual([r.status_code for r in responses], [200] * len(responses))
        self.assertEqual(
            [r.json() for r in responses], [{"status": "check_inbox"}] * len(responses)
        )
        self.assertEqual(other.status_code, 200)
        # Nur die erlaubten Mails an die Opferadresse plus die an die andere.
        self.assertEqual(deliver.call_count, auth_router._SETUP_MAILS_PER_ADDRESS + 1)
        self.assertEqual(provision.call_count, auth_router._SETUP_MAILS_PER_ADDRESS + 1)

    def test_new_and_existing_registration_responses_are_identical(self):
        new_user = SimpleNamespace(uid="new-owner", email="same@example.test")
        with (
            patch.object(auth_router, "is_password_setup_configured", return_value=True),
            patch.object(
                auth_router,
                "find_or_provision_user",
                return_value=(new_user, True),
            ),
            patch.object(auth_router, "deliver_password_setup_email"),
            patch.object(auth_router, "send_new_user_registration_notification"),
        ):
            created = self.client.post(
                "/register",
                json={"email": "same@example.test"},
            )
        with (
            patch.object(auth_router, "is_password_setup_configured", return_value=True),
            patch.object(
                auth_router,
                "find_or_provision_user",
                return_value=(SimpleNamespace(uid="existing-owner"), False),
            ),
            patch.object(auth_router, "deliver_password_setup_email"),
            patch.object(auth_router, "send_new_user_registration_notification"),
        ):
            existing = self.client.post(
                "/register",
                json={"email": "same@example.test"},
            )

        self.assertEqual(created.status_code, existing.status_code)
        self.assertEqual(created.content, existing.content)

    def test_registration_ignores_cached_client_password(self):
        user = SimpleNamespace(uid="new-owner")
        with (
            patch.object(auth_router, "is_password_setup_configured", return_value=True),
            patch.object(
                auth_router, "find_or_provision_user", return_value=(user, True)
            ) as provision,
            patch.object(auth_router, "deliver_password_setup_email"),
            patch.object(auth_router, "send_new_user_registration_notification"),
        ):
            response = self.client.post(
                "/register",
                json={"email": "new@example.test", "password": "attacker-known"},
            )

        self.assertEqual(response.status_code, 200)
        provision.assert_called_once_with("new@example.test")

    def test_registration_rejects_control_characters_before_firebase(self):
        with patch.object(auth_router, "find_or_provision_user") as provision:
            response = self.client.post(
                "/register",
                json={"email": "log-line-one\nlog-line-two@example.test"},
            )

        self.assertEqual(response.status_code, 422)
        provision.assert_not_called()

    def test_logout_clears_session_cookie(self):
        response = self.client.delete("/auth/session")
        self.assertEqual(response.status_code, 200)
        cookie = response.headers.get("set-cookie", "").lower()
        self.assertIn("session=", cookie)
        self.assertIn("max-age=0", cookie)
        self.assertEqual(response.headers.get("cache-control"), "no-store")


if __name__ == "__main__":
    unittest.main()
