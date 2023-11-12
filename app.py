import os

from cs50 import SQL
from datetime import date
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from math import trunc

from helpers import apology, login_required, lookup, usd
# Get date
today = date.today()

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Getting info about the user
    user = db.execute("SELECT * FROM users WHERE id=?", session['user_id'])

    # Declaring main dictionary
    user_hold = {}

    # Get data about all user holdings
    user_holdings = db.execute("SELECT * FROM holdings WHERE username=?", user[0]['username'])

    # Loop over all buys and add data to main dictionary
    for row in user_holdings:
        user_hold[row['symbol']] = {}
        user_hold[row['symbol']]['name'] = row['symbol']
        user_hold[row['symbol']]['quantity'] = int(row['quantity'])
        quote = lookup(row['symbol'])
        user_hold[row['symbol']]['price_now'] = float(quote['price'])

    # Send main dictionary to Jinja and render results
    return render_template("index.html", user_hold=user_hold, cash=int(user[0]['cash']))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # POST means that the user submitted de form
    if request.method == "POST":

        # Getting info about user
        user = db.execute('SELECT * FROM users WHERE id=?', session['user_id'])

        # Info about user input
        quantity = request.form.get("shares")
        symbol = request.form.get("symbol")
        result = lookup(symbol)

        try:
            int(quantity)
        except:
            return apology("Invalid input")

        # Possible errors
        if not quantity or not result or int(quantity) < 1:
            return apology("Invalid input")

        # Formating input
        symbol = symbol.upper()
        quantity = int(quantity)

        # Calculating total price of buy
        total_price = quantity * int(result["price"])
        if total_price > user[0]["cash"]:
            return apology("Can't afford")

        # Updating database, finishing transaction and return to homepage.
        user_holding = db.execute("SELECT * FROM holdings WHERE username=? AND symbol=?", user[0]['username'], symbol)
        if user_holding:
            db.execute("UPDATE holdings SET quantity=? WHERE username=? AND symbol=?",
                       (user_holding[0]['quantity'] + quantity), user[0]['username'], symbol)
        else:
            db.execute("INSERT INTO holdings (username, symbol, quantity) VALUES (?, ?, ?)", user[0]['username'], symbol, quantity)
        db.execute("INSERT INTO transactions (username, symbol, quantity, price, date, type) VALUES (?, ?, ?, ?, ?, ?)",
                   user[0]["username"], symbol, quantity, result["price"], today, 'buy')
        db.execute("UPDATE users SET cash=? WHERE id=?", (user[0]["cash"] - total_price), user[0]["id"])
        return redirect("/")

    # If method is GET, render page.
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = db.execute("SELECT * FROM users WHERE id=?", session['user_id'])
    transactions = db.execute("SELECT * FROM transactions WHERE username=?", user[0]['username'])
    print(transactions)

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # Se usuário chegou aqui via POST quer ver os resultados de 'quoted'
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        result = lookup(symbol)

        if not result:
            return apology("Invalid symbol")
        else:
            print(result)
            return render_template("quoted.html", symbol=result["symbol"], name=result["name"], price=result["price"])

    else:
        # Se o usuário chegou nessa rota via GET ele quer ver a página de 'quote'
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Limpa a sessão
    session.clear()

    # Se o usuário chegou na rota via POST significa que está tentando se logar
    if request.method == "POST":

        # Garante que o usuário inseriu 'username'
        if not request.form.get("username"):
            return apology("Must insert username")

        # Garante que usuário inseriu senha e confirmação de senha
        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Must insert password and confirmation")

        # Pesquisa no banco de dados pelo username inserido e verifica se já existe
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 0:
            return apology("Username already exists")

        # Verifica se as senhas coincidem
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if password != confirmation:
            return apology("Passwords don't match")

        # Procede ao cadastro do usuário
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))
        return redirect("/")

    else:
        # Usuário chegou via GET - Ver página de registro
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Get info about user
    user = db.execute("SELECT * FROM users WHERE id=?", session['user_id'])
    if request.method == 'POST':

        # Info about user input
        symbol = request.form.get("symbol")
        quantity = request.form.get("shares")
        holdings = db.execute("SELECT * FROM holdings WHERE username=? AND symbol=?", user[0]['username'], symbol)

        # Formatting input
        if symbol and quantity:
            symbol.upper()
            quantity = int(quantity)

        # Check for errors
        if not symbol or not quantity or quantity < 1:
            return apology("Invalid input")
        elif not holdings:
            return apology("You don't own any of that stock")
        elif holdings[0]['quantity'] < quantity:
            return apology("Not enough shares to complete transaction")
        else:
            # Updating database, finishing transaction and return to homepage.
            stock = lookup(symbol)
            total = stock['price'] * quantity
            db.execute("INSERT INTO transactions (username, symbol, quantity, price, type, date) VALUES (?, ?, ?, ?, ?, ?)",
                       user[0]['username'], symbol, quantity, stock['price'], 'sell', today)
            db.execute("UPDATE users SET cash=? WHERE username=?", total + user[0]['cash'], user[0]['username'])
            db.execute("UPDATE holdings SET quantity=? WHERE username=? AND symbol=?",
                       holdings[0]['quantity'] - quantity, user[0]['username'], symbol)
            return redirect("/")

    # If method is GET, render page.
    else:
        holdings = db.execute("SELECT * FROM holdings WHERE username=?", user[0]['username'])
        return render_template("sell.html", holdings=holdings)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Add cash to user account"""
    if request.method == "POST":

        # Get data about user
        user = db.execute("SELECT * FROM users WHERE id=?", session['user_id'])

        # Get users input
        quantity = request.form.get("quantity")

        # Check for errors
        if not quantity or int(quantity) < 1:
            return apology("Invalid input")

        # Add cash
        db.execute("UPDATE users SET cash=? WHERE username=?", user[0]['cash'] + int(quantity), user[0]['username'])

        return redirect("/")

    else:
        return render_template("add_cash.html")
