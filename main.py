from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SESSION_KEY']
# app.secret_key = '' #Required for sessions to work (Flask-Login); set in .env / Heroku config vars
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db") #from Heroku config vars (Postgres)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db' #local DB
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Config Login Manager
login_manager = LoginManager()
login_manager.init_app(app)

# Gravatar config
gravatar = Gravatar(app,
                    size=100,
                    rating='x',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# CONFIGURE TABLES
class User(UserMixin, db.Model):  #ADD UserMixin for Login Manager
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    posts = relationship("BlogPost", back_populates="author")  # read on backref (u can specify this only once)
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # Relationship config
    author_id = Column(Integer, ForeignKey('users.id'))  # "users.id" the users refers to the tablename of User.
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(250), nullable=False)
    # Relationship config
    author_id = Column(Integer, ForeignKey('users.id'))  # "users.id" the users refers to the tablename of User.
    comment_author = relationship("User", back_populates="comments")
    post_id = Column(Integer, ForeignKey('blog_posts.id'))
    parent_post = relationship("BlogPost", back_populates="comments")


db.create_all()


# Config Login manager user_loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Admin only access decorator
def admin_only(func):
    @wraps(
        func)  # funktools function wrapping because when you use a decorator, you're replacing one function with
    # another. @wraps takes a function used in a decorator and adds the functionality of copying over the function
    # name, docstring, arguments list, etc.
    def wrapper(*args, **kwargs):
        if current_user.get_id() == '1':
            return func(*args, **kwargs)
        elif not current_user.is_authenticated:
            return redirect(url_for('login'))
        else:
            abort(403)

    return wrapper


# ROUTES
# AUTH
@app.route('/register', methods=['GET', 'POST'])
def register():
    reg_form = RegisterForm()
    if reg_form.validate_on_submit():
        user = User.query.filter_by(email=reg_form.email.data).first()
        if user:
            flash('User with this Email already exists, please log in')
            return redirect(url_for('login'))
        else:
            salted_hash = generate_password_hash(reg_form.password.data, method='pbkdf2:sha256', salt_length=8)
            new_user = User(
                name=reg_form.name.data,
                email=reg_form.email.data,
                password=salted_hash,
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=reg_form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if not user:
            flash('User do not exists')
            print("USER NOT EXIST")
            return redirect(url_for('register'))  #Error message not shown in this case
        else:
            if check_password_hash(user.password, login_form.password.data):
                print("CORRECT PWD")
                login_user(user)
                print(user.is_authenticated)
                print(user.get_id())  # get_id() return str
                print(current_user.id)  # return int
                return redirect(url_for("get_all_posts"))
            else:
                flash('Wrong password')
                print("WRONG PWD")
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


# POSTS
@app.route('/')
def get_all_posts():
    all_posts = BlogPost.query.all()
    return render_template("index.html", posts=all_posts)


@app.route('/')
def get_user_posts():
    user_posts = BlogPost.query.filter_by(name=current_user)
    return render_template("index.html", posts=user_posts)


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        print('SUBMIT')
        if current_user.is_authenticated:
            print(current_user)
            print(post_id)
            new_comment = Comment(
                text=comment_form.comment.data,
                comment_author=current_user,
                parent_post=requested_post,
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash('You have to be logged in to post a comment ')
            return redirect(url_for('login'))
    return render_template("post.html", post=requested_post, form=comment_form)


@app.route("/new-post", methods=['GET', 'POST'])
@admin_only
@login_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# OTHER
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# RUN APP
# if __name__ == "__main__":
#     app.run(host='0.0.0.0', port=5000)
if __name__ == "__main__":
    app.run(debug=True,
            port=9000,
            threaded=True)
