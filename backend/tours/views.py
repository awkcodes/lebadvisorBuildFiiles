from .models import Tour, TourDay, TourOffer
from .serializers import TourSerializer, TourDaySerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import datetime


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reserve_tour(request):
    supplier = request.user.supplier
    tour_offer_id = request.data.get("tour_offer")
    tour_day_id = request.data.get("tour_day")
    number_of_reservations = int(request.data.get("number_of_reservations", 0))

    # Fetch the tour offer
    tour_offer = get_object_or_404(TourOffer, id=tour_offer_id)

    # Check if the tour belongs to the supplier making the request
    if tour_offer.tour.supplier != supplier:
        return Response(
            {"error": "You are not authorized to reserve this tour."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Fetch the tour day
    tour_day = get_object_or_404(TourDay, id=tour_day_id)

    # Check if there is enough stock
    if tour_day.stock < number_of_reservations:
        return Response(
            {"error": "Not enough stock available for this tour day."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Deduct the number of reservations from the stock
    tour_day.stock -= number_of_reservations
    tour_day.save()

    return Response(
        {"success": "Reservation completed successfully."}, status=status.HTTP_200_OK
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def block_tourday(request):
    supplier = request.user.supplier  # Assuming the user has a related supplier profile
    tour_id = request.data.get("tour_id")
    day_str = request.data.get("day")

    # Convert the day string to a date object
    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Fetch the tour
    tour = get_object_or_404(Tour, id=tour_id)

    # Check if the tour belongs to the supplier making the request
    if tour.supplier != supplier:
        return Response(
            {"error": "You are not authorized to block tour days for this tour."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Fetch all tour days on the specified day for this tour
    tour_days = TourDay.objects.filter(tour_offer__tour=tour, day=day)

    if not tour_days.exists():
        return Response(
            {"error": "No tour days found for the specified day."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Set the stock of all tour days on this day to 0
    tour_days.update(stock=0)

    return Response(
        {"success": f"All tour days on {day_str} have been blocked."},
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_tours(request):
    current_time = timezone.now()
    packages = Tour.objects.filter(available_to__gte=current_time)[:20]
    serializer = TourSerializer(packages, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_tours(request):
    current_time = timezone.now()
    packages = Tour.objects.filter(available_to__gte=current_time)
    serializer = TourSerializer(packages, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_tour(request, pk):
    package = Tour.objects.get(pk=pk)
    serializer = TourSerializer(package)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_tour_days(request, tour_offer_id):
    try:
        tour_offer = TourOffer.objects.get(pk=tour_offer_id)
        tour_days = TourDay.objects.filter(tour_offer=tour_offer)
        serializer = TourDaySerializer(tour_days, many=True)
        return Response(serializer.data)
    except TourOffer.DoesNotExist:
        return Response(
            {"error": "Tour offer not found."}, status=status.HTTP_404_NOT_FOUND
        )
