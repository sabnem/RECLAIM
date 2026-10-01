"""Read-only queries shared by reporting views."""

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import RecoveredItem, UserProfile


def return_statistics_for(user):
    """Compute totals in one query, preserving the dashboard's context contract."""
    now = timezone.now()
    totals = RecoveredItem.objects.aggregate(
        total_recovered=Count("id"),
        total_rated=Count("rating"),
        avg_rating=Avg("rating"),
        user_recovered=Count("id", filter=Q(owner=user)),
        user_returned=Count("id", filter=Q(finder=user)),
        user_avg_rating=Avg("rating", filter=Q(finder=user)),
        recent_recovered=Count("id", filter=Q(recovered_date__gte=now - timedelta(days=30))),
    )
    totals["avg_rating"] = round(totals["avg_rating"] or 0, 2)
    totals["user_avg_rating"] = round(totals["user_avg_rating"] or 0, 2)
    distribution = {str(rating): 0 for rating in range(5, 0, -1)}
    for row in RecoveredItem.objects.filter(rating__isnull=False).order_by().values("rating").annotate(count=Count("id")):
        distribution[str(row["rating"])] = row["count"]
    return {
        **totals,
        "rating_distribution": distribution,
        "top_finders": UserProfile.objects.filter(total_returns__gt=0)
            .select_related("user").order_by("-reputation_score", "-total_returns")[:10],
        "recent_recoveries": RecoveredItem.objects.select_related("item", "owner", "finder")
            .order_by("-recovered_date")[:10],
        "monthly_stats": RecoveredItem.objects.filter(recovered_date__gte=now - timedelta(days=180))
            .annotate(month=TruncMonth("recovered_date")).values("month")
            .annotate(count=Count("id")).order_by("month"),
    }
