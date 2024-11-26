from .models import Package, PackageDay, PackageOffer
from .serializers import PackageSerializer, PackageDaySerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from datetime import datetime


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def block_package_day(request):
    supplier = request.user.supplier  # Assuming the user has a related supplier profile
    package_id = request.data.get("package_id")
    day_str = request.data.get("day")

    # Convert the day string to a date object
    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Fetch the package
    package = get_object_or_404(Package, id=package_id)

    # Check if the package belongs to the supplier making the request
    if package.supplier != supplier:
        return Response(
            {"error": "You are not authorized to block package days for this package."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Fetch all package days on the specified day for this package
    package_days = PackageDay.objects.filter(package_offer__package=package, day=day)

    if not package_days.exists():
        return Response(
            {"error": "No package days found for the specified day."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Set the stock of all package days on this day to 0
    package_days.update(stock=0)

    return Response(
        {"success": f"All package days on {day_str} have been blocked."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reserve_package(request):
    supplier = request.user.supplier
    package_offer_id = request.data.get("package_offer")
    package_day_id = request.data.get("package_day")
    number_of_reservations = int(request.data.get("number_of_reservations", 0))

    # Fetch the package offer
    package_offer = get_object_or_404(PackageOffer, id=package_offer_id)

    # Check if the package belongs to the supplier making the request
    if package_offer.package.supplier != supplier:
        return Response(
            {"error": "You are not authorized to reserve this package."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Fetch the package day
    package_day = get_object_or_404(PackageDay, id=package_day_id)

    # Check if there is enough stock
    if package_day.stock < number_of_reservations:
        return Response(
            {"error": "Not enough stock available for this package day."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Deduct the number of reservations from the stock
    package_day.stock -= number_of_reservations
    package_day.save()

    return Response(
        {"success": "Reservation completed successfully."}, status=status.HTTP_200_OK
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_packages(request):
    current_time = timezone.now()
    packages = Package.objects.filter(available_to__gte=current_time)[:20]
    serializer = PackageSerializer(packages, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_packages(request):
    current_time = timezone.now()
    packages = Package.objects.filter(available_to__gte=current_time)
    serializer = PackageSerializer(packages, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_package(request, pk):
    package = Package.objects.get(pk=pk)
    serializer = PackageSerializer(package)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_package_days(request, package_offer_id):
    try:
        package_offer = PackageOffer.objects.get(pk=package_offer_id)
        package_days = PackageDay.objects.filter(package_offer=package_offer)
        serializer = PackageDaySerializer(package_days, many=True)
        return Response(serializer.data)
    except PackageOffer.DoesNotExist:
        return Response(
            {"error": "Package offer not found."}, status=status.HTTP_404_NOT_FOUND
        )
