from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from notifications.models import Notification
from booking.models import ActivityBooking, PackageBooking, TourBooking
from activities.models import Period, Activity
from packages.models import Package, PackageDay, PackageOffer
from tours.models import Tour, TourDay, TourOffer
from users.models import Supplier, Customer
from booking.serializers import (
    ActivityBookingSerializer,
    PackageBookingSerializer,
    TourBookingSerializer,
)
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, F
from django.db.models.functions import ExtractMonth  # Import ExtractMonth
from activities.serializers import ActivitySerializer
from tours.serializers import TourSerializer
from packages.serializers import PackageSerializer
from collections import defaultdict


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def supplier_offers(request):
    user = request.user
    try:
        supplier = user.supplier
    except Supplier.DoesNotExist:
        return Response(
            {"detail": "You are not authorized to view this information."}, status=403
        )

    # Fetching the offers related to the supplier
    activity_offers = Activity.objects.filter(supplier=supplier)
    tour_offers = Tour.objects.filter(supplier=supplier)
    package_offers = Package.objects.filter(supplier=supplier)

    activity_serialized = ActivitySerializer(activity_offers, many=True)
    tour_serialized = TourSerializer(tour_offers, many=True)
    package_serialized = PackageSerializer(package_offers, many=True)

    data = {
        "activity_offers": activity_serialized.data,
        "tour_offers": tour_serialized.data,
        "package_offers": package_serialized.data,
    }

    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def supplier_dashboard(request):
    user = request.user
    try:
        supplier = user.supplier
    except Supplier.DoesNotExist:
        return Response(
            {"detail": "You are not authorized to view this information."}, status=403
        )

    # My offers
    activities = supplier.activity_set.all()
    tours = supplier.tour_set.all()
    packages = supplier.package_set.all()

    activity_serialized = ActivitySerializer(activities, many=True)
    tour_serialized = TourSerializer(tours, many=True)
    package_serialized = PackageSerializer(packages, many=True)

    # Total sales
    total_sales = (
        (
            ActivityBooking.objects.filter(
                period__activity_offer__activity__supplier=supplier, confirmed=True
            ).aggregate(total_sales=Sum("quantity"))["total_sales"]
            or 0
        )
        + (
            TourBooking.objects.filter(
                tourday__tour_offer__tour__supplier=supplier, confirmed=True
            ).aggregate(total_sales=Sum("quantity"))["total_sales"]
            or 0
        )
        + (
            PackageBooking.objects.filter(
                package_offer__package__supplier=supplier, confirmed=True
            ).aggregate(total_sales=Sum("quantity"))["total_sales"]
            or 0
        )
    )

    # Confirmed bookings combined
    confirmed_bookings = (
        (
            ActivityBooking.objects.filter(
                period__activity_offer__activity__supplier=supplier, confirmed=True
            ).count()
        )
        + (
            TourBooking.objects.filter(
                tourday__tour_offer__tour__supplier=supplier, confirmed=True
            ).count()
        )
        + (
            PackageBooking.objects.filter(
                package_offer__package__supplier=supplier, confirmed=True
            ).count()
        )
    )

    # Confirmed bookings this month
    start_of_month = timezone.now().replace(day=1)
    confirmed_bookings_this_month = (
        (
            ActivityBooking.objects.filter(
                period__activity_offer__activity__supplier=supplier,
                confirmed=True,
                created_at__gte=start_of_month,
            ).count()
        )
        + (
            TourBooking.objects.filter(
                tourday__tour_offer__tour__supplier=supplier,
                confirmed=True,
                created_at__gte=start_of_month,
            ).count()
        )
        + (
            PackageBooking.objects.filter(
                package_offer__package__supplier=supplier,
                confirmed=True,
                created_at__gte=start_of_month,
            ).count()
        )
    )

    # Unconfirmed bookings
    unconfirmed_bookings = (
        (
            ActivityBooking.objects.filter(
                period__activity_offer__activity__supplier=supplier, confirmed=False
            ).count()
        )
        + (
            TourBooking.objects.filter(
                tourday__tour_offer__tour__supplier=supplier, confirmed=False
            ).count()
        )
        + (
            PackageBooking.objects.filter(
                package_offer__package__supplier=supplier, confirmed=False
            ).count()
        )
    )

    # Unconfirmed bookings this month
    unconfirmed_bookings_this_month = (
        (
            ActivityBooking.objects.filter(
                period__activity_offer__activity__supplier=supplier,
                confirmed=False,
                created_at__gte=start_of_month,
            ).count()
        )
        + (
            TourBooking.objects.filter(
                tourday__tour_offer__tour__supplier=supplier,
                confirmed=False,
                created_at__gte=start_of_month,
            ).count()
        )
        + (
            PackageBooking.objects.filter(
                package_offer__package__supplier=supplier,
                confirmed=False,
                created_at__gte=start_of_month,
            ).count()
        )
    )

    # Today's customers
    today = timezone.now().date()
    todays_customers = (
        list(
            ActivityBooking.objects.filter(
                period__activity_offer__activity__supplier=supplier,
                period__day=today,
            ).values_list(
                "customer__user__username",
                "period__activity_offer__activity__title",
                "period__time_from",
            )
        )
        + list(
            TourBooking.objects.filter(
                tourday__tour_offer__tour__supplier=supplier,
                tourday__day=today,
            ).values_list(
                "customer__user__username",
                "tourday__tour_offer__tour__title",
                "tourday__tour_offer__tour__pickup_time",
            )
        )
        + list(
            PackageBooking.objects.filter(
                package_offer__package__supplier=supplier,
                start_date=today,
            ).values_list(
                "customer__user__username",
                "package_offer__package__title",
                "package_offer__package__pickup_time",
            )
        )
    )

    data = {
        "my_offers": {
            "activities": activity_serialized.data,
            "tours": tour_serialized.data,
            "packages": package_serialized.data,
        },
        "total_sales": total_sales,
        "confirmed_bookings": confirmed_bookings,
        "confirmed_bookings_this_month": confirmed_bookings_this_month,
        "unconfirmed_bookings": unconfirmed_bookings,
        "unconfirmed_bookings_this_month": unconfirmed_bookings_this_month,
        "todays_customers": todays_customers,
    }

    return Response(data)


# Customer views for activity bookings
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customer_activity_bookings(request):
    customer = get_object_or_404(Customer, user=request.user)
    bookings = ActivityBooking.objects.filter(customer=customer)
    serializer = ActivityBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Supplier views for activity bookings
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def supplier_activity_bookings(request):
    supplier = get_object_or_404(Supplier, user=request.user)
    activities = Activity.objects.filter(supplier=supplier)
    periods = Period.objects.filter(activity_offer__activity__in=activities)
    bookings = ActivityBooking.objects.filter(period__in=periods)
    serializer = ActivityBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_activity_booking(request, booking_id):
    supplier = get_object_or_404(Supplier, user=request.user)
    booking = get_object_or_404(ActivityBooking, id=booking_id)
    period = get_object_or_404(Period, pk=booking.period_id)
    if booking.period.activity_offer.activity.supplier != supplier:
        return Response(
            {"detail": "Not authorized to confirm this booking."},
            status=status.HTTP_403_FORBIDDEN,
        )

    booking.confirmed = True
    booking.generate_qr_code()
    period.stock -= booking.quantity
    period.save()
    booking.save()

    Notification.objects.create(
        user=booking.customer.user,
        message=f"Activity {period.activity_offer.activity.title} got confirmed",
    )
    serializer = ActivityBookingSerializer(booking)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_payment(request, booking_id):
    supplier = get_object_or_404(Supplier, user=request.user)
    booking = get_object_or_404(ActivityBooking, id=booking_id)
    if booking.period.activity_offer.activity.supplier != supplier:
        return Response(
            {"detail": "Not authorized to confirm payment for this booking."},
            status=status.HTTP_403_FORBIDDEN,
        )

    booking.paid = True
    booking.save()
    serializer = ActivityBookingSerializer(booking)

    Notification.objects.create(
        user=booking.customer.user, message="Activity Booking got paid"
    )
    Notification.objects.create(
        user=booking.period.activity_offer.activity.supplier.user,
        message="Activity Booking got paid",
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


# Customer views for package bookings
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customer_package_bookings(request):
    customer = get_object_or_404(Customer, user=request.user)
    bookings = PackageBooking.objects.filter(customer=customer)
    serializer = PackageBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Supplier views for package bookings
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def supplier_packages_bookings(request):
    supplier = get_object_or_404(Supplier, user=request.user)
    packages = Package.objects.filter(supplier=supplier)
    bookings = PackageBooking.objects.filter(package_offer__package__in=packages)
    serializer = PackageBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_package_booking(request, booking_id):
    supplier = get_object_or_404(Supplier, user=request.user)
    booking = get_object_or_404(PackageBooking, id=booking_id)

    if booking.package_offer.package.supplier != supplier:
        return Response(
            {"detail": "Not authorized to confirm this booking."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if booking.confirmed:
        return Response(
            {"detail": "Booking is already confirmed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    package = booking.package_offer.package
    start_date = booking.start_date
    end_date = start_date + timedelta(days=package.period - 1)
    package_days = PackageDay.objects.filter(
        package_offer=booking.package_offer, day__range=(start_date, end_date)
    )

    for day in package_days:
        if day.stock < 1:
            return Response(
                {"error": f"No available stock for {day.day}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    for day in package_days:
        day.stock -= booking.quantity
        day.save()

    booking.confirmed = True
    booking.generate_qr_code()
    booking.save()
    Notification.objects.create(
        user=booking.customer.user,
        message=f"Package {package.title} got confirmed, enjoy your time",
    )
    serializer = PackageBookingSerializer(booking)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_package_payment(request, booking_id):
    supplier = get_object_or_404(Supplier, user=request.user)
    booking = get_object_or_404(PackageBooking, id=booking_id)
    if booking.package_offer.package.supplier != supplier:
        return Response(
            {"detail": "Not authorized to confirm payment for this booking."},
            status=status.HTTP_403_FORBIDDEN,
        )

    booking.paid = True
    booking.save()
    serializer = PackageBookingSerializer(booking)

    Notification.objects.create(
        user=booking.customer.user, message="Package Booking got paid"
    )
    Notification.objects.create(
        user=booking.package_offer.package.supplier.user,
        message="Package Booking got paid",
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


# Customer views for tour bookings
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customer_tour_bookings(request):
    customer = get_object_or_404(Customer, user=request.user)
    bookings = TourBooking.objects.filter(customer=customer)
    serializer = TourBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Supplier views for tour bookings
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def supplier_tours_bookings(request):
    supplier = get_object_or_404(Supplier, user=request.user)
    tours = Tour.objects.filter(supplier=supplier)
    days = TourDay.objects.filter(tour_offer__tour__in=tours)
    bookings = TourBooking.objects.filter(tourday__in=days)
    serializer = TourBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_tour_booking(request, booking_id):
    supplier = get_object_or_404(Supplier, user=request.user)
    booking = get_object_or_404(TourBooking, id=booking_id)
    if booking.tourday.tour_offer.tour.supplier != supplier:
        return Response(
            {"detail": "Not authorized to confirm this booking."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if booking.confirmed:
        return Response(
            {"detail": "Booking is already confirmed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tourday = booking.tourday
    if tourday.stock < 1:
        return Response(
            {"error": "No available stock for this tour day."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tourday.stock -= booking.quantity
    tourday.save()

    booking.confirmed = True
    booking.generate_qr_code()
    booking.save()

    Notification.objects.create(
        user=booking.customer.user, message="Tour got confirmed, enjoy your time"
    )
    serializer = TourBookingSerializer(booking)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_tour_payment(request, booking_id):
    supplier = get_object_or_404(Supplier, user=request.user)
    booking = get_object_or_404(TourBooking, id=booking_id)
    if booking.tourday.tour_offer.tour.supplier != supplier:
        return Response(
            {"detail": "Not authorized to confirm payment for this booking."},
            status=status.HTTP_403_FORBIDDEN,
        )

    booking.paid = True
    booking.save()
    serializer = TourBookingSerializer(booking)
    Notification.objects.create(
        user=booking.customer.user, message="Tour Booking got paid"
    )
    Notification.objects.create(
        user=booking.tourday.tour_offer.tour.supplier.user,
        message="Tour Booking got paid",
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


# Utility function to fill in missing months with zero values
def fill_missing_months(data, value_key):
    result = {month: 0 for month in range(1, 13)}
    for item in data:
        result[item["month"]] += item[value_key]
    return result


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bookings_per_month(request):
    supplier = request.user.supplier
    start_of_year = timezone.now().replace(month=1, day=1)

    # Aggregating bookings per month for activities
    activity_bookings = (
        ActivityBooking.objects.filter(
            period__activity_offer__activity__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    # Aggregating bookings per month for packages
    package_bookings = (
        PackageBooking.objects.filter(
            package_offer__package__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    # Aggregating bookings per month for tours
    tour_bookings = (
        TourBooking.objects.filter(
            tourday__tour_offer__tour__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    # Combine all bookings data and fill in missing months
    combined_data = fill_missing_months(
        list(activity_bookings) + list(package_bookings) + list(tour_bookings),
        value_key="count",
    )

    # Convert dictionary to list of tuples sorted by month
    combined_data_sorted = sorted(combined_data.items())

    return Response(combined_data_sorted)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customers_per_month(request):
    supplier = request.user.supplier
    start_of_year = timezone.now().replace(month=1, day=1)

    # Aggregating customer IDs per month for activities
    activity_customers = (
        ActivityBooking.objects.filter(
            period__activity_offer__activity__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .values("month", "customer__user__id")
        .order_by("month")
    )

    # Aggregating customer IDs per month for packages
    package_customers = (
        PackageBooking.objects.filter(
            package_offer__package__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .values("month", "customer__user__id")
        .order_by("month")
    )

    # Aggregating customer IDs per month for tours
    tour_customers = (
        TourBooking.objects.filter(
            tourday__tour_offer__tour__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .values("month", "customer__user__id")
        .order_by("month")
    )

    # Combine all customer data
    combined_customers = (
        list(activity_customers) + list(package_customers) + list(tour_customers)
    )

    # Use a dictionary to count unique customers per month
    monthly_customers = {}
    for item in combined_customers:
        month = item["month"]
        customer_id = item["customer__user__id"]
        if month not in monthly_customers:
            monthly_customers[month] = set()
        monthly_customers[month].add(customer_id)

    # Convert the set of customer IDs to counts
    monthly_customer_counts = {
        month: len(customer_set) for month, customer_set in monthly_customers.items()
    }

    # Fill in missing months with 0
    full_monthly_counts = {
        month: monthly_customer_counts.get(month, 0) for month in range(1, 13)
    }

    # Convert to list of tuples sorted by month
    combined_data_sorted = sorted(full_monthly_counts.items())

    return Response(combined_data_sorted)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sales_per_month(request):
    supplier = request.user.supplier
    start_of_year = timezone.now().replace(month=1, day=1)

    # Aggregating sales per month for activities
    activity_sales = (
        ActivityBooking.objects.filter(
            period__activity_offer__activity__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .annotate(sales=Sum(F("quantity") * F("period__activity_offer__price")))
        .values("month", "sales")
        .order_by("month")
    )

    # Aggregating sales per month for packages
    package_sales = (
        PackageBooking.objects.filter(
            package_offer__package__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .annotate(sales=Sum(F("quantity") * F("package_offer__price")))
        .values("month", "sales")
        .order_by("month")
    )

    # Aggregating sales per month for tours
    tour_sales = (
        TourBooking.objects.filter(
            tourday__tour_offer__tour__supplier=supplier,
            confirmed=True,
            created_at__gte=start_of_year,
        )
        .annotate(month=ExtractMonth("created_at"))
        .annotate(sales=Sum(F("quantity") * F("tourday__tour_offer__price")))
        .values("month", "sales")
        .order_by("month")
    )

    # Combine all sales data and fill in missing months
    combined_sales = fill_missing_months(
        list(activity_sales) + list(package_sales) + list(tour_sales), value_key="sales"
    )

    # Convert dictionary to list of tuples sorted by month
    combined_sales_sorted = sorted(combined_sales.items())

    return Response(combined_sales_sorted)
