from .models import Activity, Period, ActivityOffer
from django.shortcuts import get_object_or_404
from .serializers import ActivitySerializer, PeriodSerializer, ActivityOfferSerializer
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def block_activity_day(request):
    supplier = request.user.supplier
    activity_id = request.data.get("activity_id")
    day_str = request.data.get("day")
    # Convert the day string to a date object
    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Fetch the activity
    activity = get_object_or_404(Activity, id=activity_id)

    # Check if the activity belongs to the supplier making the request
    if activity.supplier != supplier:
        return Response(
            {"error": "You are not authorized to block periods for this activity."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Fetch all periods on the specified day for this activity
    periods = Period.objects.filter(activity_offer__activity=activity, day=day)

    if not periods.exists():
        return Response(
            {"error": "No periods found for the specified day."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Set the stock of all periods on this day to 0
    periods.update(stock=0)

    return Response(
        {"success": f"All periods on {day_str} have been blocked."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reserve_activity(request):
    supplier = request.user.supplier
    activity_offer_id = request.data.get("activity_offer")
    period_id = request.data.get("period")
    number_of_reservations = int(request.data.get("number_of_reservations", 0))

    # Fetch the activity offer
    activity_offer = get_object_or_404(ActivityOffer, id=activity_offer_id)

    # Check if the activity belongs to the supplier making the request
    if activity_offer.activity.supplier != supplier:
        return Response(
            {"error": "You are not authorized to reserve this activity."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Fetch the period
    period = get_object_or_404(Period, id=period_id)

    # Check if there is enough stock
    if period.stock < number_of_reservations:
        return Response(
            {"error": "Not enough stock available for this period."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Deduct the number of reservations from the stock
    period.stock -= number_of_reservations
    period.save()

    return Response(
        {"success": "Reservation completed successfully."}, status=status.HTTP_200_OK
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_offers_by_activity(request, activity_id):
    try:
        activity = Activity.objects.get(pk=activity_id)
    except Activity.DoesNotExist:
        return Response(
            {"error": "Activity not found"}, status=status.HTTP_404_NOT_FOUND
        )

    offers = ActivityOffer.objects.filter(activity=activity)
    serializer = ActivityOfferSerializer(offers, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_activities(request):
    # timezone of the server, should be set to Lebanon
    current_time = timezone.now()
    # exclude items that their time has passed
    activities = Activity.objects.filter(available_to__gte=current_time)
    serializer = ActivitySerializer(activities, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_activity(request, pk):
    activity = Activity.objects.get(pk=pk)
    serializer = ActivitySerializer(activity)
    return Response(serializer.data)


# main page activities, exclude passed and only 20 ordered
@api_view(["GET"])
@permission_classes([AllowAny])
def get_activities(request):
    current_time = timezone.now()
    activities = Activity.objects.filter(available_to__gte=current_time)[:20]
    serializer = ActivitySerializer(activities, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_periods_by_offer_and_day(request, offer_id, day):
    try:
        offer = ActivityOffer.objects.get(pk=offer_id)
    except ActivityOffer.DoesNotExist:
        return Response({"error": "Offer not found"}, status=status.HTTP_404_NOT_FOUND)

    periods = Period.objects.filter(activity_offer=offer, day=day, stock__gt=0)
    serializer = PeriodSerializer(periods, many=True)
    return Response(serializer.data)
