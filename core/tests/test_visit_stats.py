from django.test import TestCase
from django.urls import reverse

from core.models import DailyVisitStat


class VisitStatsTests(TestCase):
    def test_daily_hits_increase_per_request(self):
        home_url = reverse("home")
        self.client.get(home_url)
        self.client.get(home_url)

        stat = DailyVisitStat.objects.first()
        self.assertIsNotNone(stat)
        self.assertEqual(stat.total_hits, 2)
        self.assertEqual(stat.unique_sessions, 1)
