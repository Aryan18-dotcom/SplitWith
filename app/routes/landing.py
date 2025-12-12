from flask import Blueprint, render_template

land = Blueprint("landing_page", __name__, template_folder="templates")


@land.route('/', methods=["GET", "POST"])
def landing():
    return render_template("index.html")