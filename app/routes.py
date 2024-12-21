# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Movie, Cinema, ScreeningTime, Booking, Hall
from app.forms import RegistrationForm, LoginForm, BookingForm

main = Blueprint("main", __name__)
auth = Blueprint("auth", __name__)
import app

@main.route("/")
def home():
    movies = Movie.query.filter_by(is_current=True).limit(6).all()
    # top_rated_movies = Movie.query.order_by(Movie.rating.desc()).limit(6).all()
    # most_commented_movies = (
    #     Movie.query.order_by(Movie.comments_count.desc()).limit(6).all()
    # )

    return render_template(
        "home.html",
        movies=movies,
        top_rated_movies=[],
        most_commented_movies=[],
    )


@main.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    screenings = ScreeningTime.query.filter_by(movie_id=movie_id).all()
    return render_template("movie_detail.html", movie=movie, screenings=screenings)


@main.route("/favorite/<int:movie_id>", methods=["POST"])
@login_required
def toggle_favorite(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if movie in current_user.favorite_movies:
        current_user.favorite_movies.remove(movie)
    else:
        current_user.favorite_movies.append(movie)
    db.session.commit()
    return redirect(url_for("main.movie_detail", movie_id=movie_id))


@main.route("/book/<int:screening_id>", methods=["GET", "POST"])
@login_required
def book_seat(screening_id):
    screening = ScreeningTime.query.get_or_404(screening_id)
    form = BookingForm()

    bookings = Booking.query.filter_by(screening_id=screening_id).all()
    screening.cinema_id
    total_seats =  Hall.query.with_entities(Hall.size).filter_by(id = screening.hall.id).one()[0]
    # 定義座位表（假設一個固定座位結構）
    seats_per_row = 10
    total_rows = total_seats // seats_per_row
    
    seating_chart = [ # 初始化座位表
        [{'seat_number': row * seats_per_row + seat + 1, 'status': 'available'} for seat in range(seats_per_row)]
        for row in range(total_rows)
    ]
    # app.logging.debug(seating_chart)
    # 標記已預約的座位
    for booking in bookings:
        seat_number = int(booking.seat_number)
        row = (seat_number - 1) // seats_per_row
        seat = (seat_number - 1) % seats_per_row

        # 標記該座位為已預約
        if 0 <= row < total_rows and 0 <= seat < seats_per_row:
            seating_chart[row][seat]['status'] = 'booked'
        else:
            print(f"Invalid seat number: {seat_number}")


    # 根據 screening_id 過濾相關資料並生成選項
    form.cinema.choices = [
        (screening.cinema.id, screening.cinema.name)
    ]

    form.hall.choices = [
        (screening.hall.id, screening.hall.name)
    ] 
    
    form.movie.choices = [
        (screening.movie.id, screening.movie.title)
    ]  
    
    form.screening_time.choices = [
        (screening.id, screening.date)
    ] 
    bill_detail = {'name':User.query.filter_by(id=current_user.id).first().username,
                   'cinema': screening.cinema.name,
                    'hall' : screening.hall.name,
                    'movie': screening.movie.title, 
                   'id':[],
                   'price':[]}
    if request.method == 'POST':
        app.logging.debug(f"Form data: {request.form}") ## 還要設定 cinima 和 movie screening_time
        if form.validate_on_submit():
            app.logging.debug(form.seat_number.data.split(','))
            for seat in form.seat_number.data.split(','):
                # Check if seat is already booked
                existing_booking = Booking.query.filter_by(
                    screening_id=screening_id, seat_number=seat
                ).first()

                if existing_booking:
                    flash("This seat is already booked", "danger")
                    return render_template("booking.html", form=form, screening=screening)

                # Create new booking
                booking = Booking(
                    user_id=current_user.id,
                    screening_id=screening_id,
                    seat_number=seat,
                )
                db.session.add(booking)
                db.session.commit()
                flash("Booking successful!", "success")
                bill_detail["id"].append(booking.id)
                bill_detail["price"].append(ScreeningTime.query.with_entities(ScreeningTime.price).filter_by(id = screening_id).one()[0])
        
            app.logging.debug(bill_detail)
            session['bill_detail'] = bill_detail
            return redirect(url_for("main.payment"))
        else:
            app.logging.debug(f"Form errors: {form.errors}")

    return render_template("booking.html", form=form, screening=screening,seating_chart=seating_chart)

@main.route("/book/bill/", methods=["GET", "POST"])
@login_required
def payment():
    bill_detail = session.get('bill_detail', [])
    app.logging.debug(bill_detail)
    name = bill_detail['name']
    ids = bill_detail['id']
    price = bill_detail['price']
    price_sum = sum(price)
    return render_template("bill.html"
                           ,name=name
                           ,book_id=ids
                           ,price=price
                           ,price_sum=price_sum
                           ,cinema=bill_detail['cinema']
                           ,hall=bill_detail['hall']
                           ,movie=bill_detail['movie'])
    return redirect(url_for("main.home"))


@auth.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful!", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)


@auth.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("main.home"))
        else:
            flash("Login unsuccessful. Please check email and password", "danger")
    return render_template("login.html", form=form)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.home"))


@main.route("/search")
def search():
    query = request.args.get("query", "")
    if query:
        movies = Movie.query.filter(Movie.title.ilike(f"%{query}%")).all()
    else:
        movies = []
    return render_template("search_results.html", movies=movies, query=query)
