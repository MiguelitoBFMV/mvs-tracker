from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PlatformAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="test-owner",
        )

    def test_home_is_public(self):
        response = self.client.get(
            reverse("core:home")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "core/home.html",
        )

    def test_login_page_is_available(self):
        response = self.client.get(
            reverse("login")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "registration/login.html",
        )

    def test_authenticated_owner_can_open_home(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:home")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "test-owner",
        )

    def test_home_links_to_available_modules(self):
        response = self.client.get(
            reverse("core:home")
        )

        self.assertContains(
            response,
            reverse("mal_insights:dashboard"),
        )
        self.assertContains(
            response,
            reverse("games:dashboard"),
        )

    def test_home_displays_all_five_modules(self):
        response = self.client.get(
            reverse("core:home")
        )

        expected_modules = (
            "MAL Insights",
            "Game Kiroku",
            "Watchroom",
            "Music",
            "Hibi Log",
        )

        for module_name in expected_modules:
            with self.subTest(module_name=module_name):
                self.assertContains(
                    response,
                    module_name,
                )

    def test_hibi_log_is_presented_as_cross_module_hub(self):
        response = self.client.get(
            reverse("core:home")
        )

        self.assertContains(
            response,
            "Daily Activity Hub",
        )
        self.assertContains(
            response,
            "Connected to every tracking module",
        )
        self.assertContains(
            response,
            "日々ログ",
        )

    def test_planned_modules_are_not_links(self):
        response = self.client.get(
            reverse("core:home")
        )

        self.assertNotContains(
            response,
            'href="/watchroom/"',
        )
        self.assertNotContains(
            response,
            'href="/music/"',
        )
        self.assertNotContains(
            response,
            'href="/activity/"',
        )
