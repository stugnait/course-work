from bson.errors import InvalidId
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from pymongo import MongoClient
from datetime import datetime, date
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SubmitField, SelectField,
                     IntegerField, DateField, TextAreaField, FieldList, FormField)
from wtforms.fields.choices import SelectMultipleField
from wtforms.fields.numeric import DecimalField
from wtforms.validators import DataRequired, Length, Optional, Email
from functools import wraps
import datetime

# Конфігурація додатку
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ваш_секретний_ключ'
app.config['MONGO_URI'] = 'mongodb://localhost:27017/Trader'

client = MongoClient('localhost', 27017)
db = client['Trader']

# Налаштування Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Модель користувача
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.password_hash = user_data['password']
        self.role = user_data['role']

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get(user_id):
        user_data = db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


# Форми

class SupplierOrderItemForm(FlaskForm):
    product_id = StringField('ID товару', validators=[DataRequired()])
    product_name = StringField('Назва товару', validators=[DataRequired()])
    quantity = IntegerField('Кількість', validators=[DataRequired()])


class SupplierOrderForm(FlaskForm):
    supplier_id = SelectField('Постачальник', coerce=str, validators=[DataRequired()], choices=[])
    order_date = DateField('Дата замовлення', validators=[DataRequired()], default=datetime.date.today)
    selected_requests = SelectMultipleField('Заявки з торговельних точок', coerce=str, choices=[])
    products_ordered = FieldList(FormField(SupplierOrderItemForm), min_entries=1)
    submit = SubmitField('Зберегти')

class LoginForm(FlaskForm):
    username = StringField('Логін', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Увійти')


class RegisterForm(FlaskForm):
    username = StringField('Логін', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    role = SelectField('Роль', choices=[
        ('owner', 'Власник'),
        ('admin', 'Адміністратор'),
        ('operator', 'Оператор'),
        ('guest', 'Гість')
    ], validators=[DataRequired()])
    submit = SubmitField('Зареєструватися')


class TradePointForm(FlaskForm):
    name = StringField('Назва', validators=[DataRequired()])
    type = SelectField('Тип', choices=[('універмаг', 'Універмаг'), ('магазин', 'Магазин'),
                                       ('кіоск', 'Кіоск'), ('лоток', 'Лоток')],
                       validators=[DataRequired()])
    size = IntegerField('Розмір (м²)', validators=[DataRequired()])
    rent_payments = IntegerField('Платежі за оренду', validators=[DataRequired()])
    utility_payments = IntegerField('Комунальні послуги', validators=[DataRequired()])
    number_of_counters = IntegerField('Кількість прилавків', validators=[DataRequired()])
    halls = StringField('Зали (через кому)', validators=[Optional()])
    sections = StringField('Секції (через кому)', validators=[Optional()])
    submit = SubmitField('Зберегти')


class SellerForm(FlaskForm):
    name = StringField('Ім\'я', validators=[DataRequired()])
    trade_point_id = SelectField('Торговельна точка', coerce=str, validators=[DataRequired()])
    salary = IntegerField('Заробітна плата (грн)', validators=[DataRequired()])
    submit = SubmitField('Зберегти')


class SupplierForm(FlaskForm):
    name = StringField('Назва', validators=[DataRequired()])
    contact_info = TextAreaField('Контактна інформація', validators=[DataRequired()])
    submit = SubmitField('Зберегти')


class ProductForm(FlaskForm):
    name = StringField('Назва', validators=[DataRequired()])
    description = TextAreaField('Опис', validators=[Optional()])
    suppliers = SelectField('Постачальники', coerce=str, validators=[DataRequired()], choices=[])
    submit = SubmitField('Зберегти')



class CustomerForm(FlaskForm):
    name = StringField('Ім\'я', validators=[DataRequired()])
    characteristics = TextAreaField('Характеристики', validators=[Optional()])
    submit = SubmitField('Зберегти')


class RequestItemForm(FlaskForm):
    product_id = SelectField('Товар', coerce=str, validators=[DataRequired()])
    quantity = IntegerField('Кількість', validators=[DataRequired()])


class RequestForm(FlaskForm):
    trade_point_id = SelectField('Торговельна точка', coerce=str, choices=[])
    date = DateField('Дата', default=datetime.date.today)
    products_requested = FieldList(FormField(RequestItemForm), min_entries=1)
    submit = SubmitField('Зберегти')


# Декоратор для перевірки ролі
def role_required(role):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Будь ласка, увійдіть до системи.', 'warning')
                return redirect(url_for('login'))
            if current_user.role != role and role not in ['owner', 'admin']:
                flash('У вас немає прав доступу до цієї сторінки.', 'danger')
                return redirect(url_for('access_denied'))
            return f(*args, **kwargs)

        return decorated_function

    return wrapper


# Маршрути
@app.route('/')
@login_required
def index():
    return render_template('index.html')


# Маршрути для автентифікації
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user_data = db.users.find_one({'username': form.username.data})
        if user_data and User(user_data).check_password(form.password.data):
            user = User(user_data)
            login_user(user)
            flash('Ви успішно увійшли до системи.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неправильний логін або пароль.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Ви вийшли з системи.', 'success')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Ви вже увійшли в систему.', 'info')
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = db.users.find_one({'username': form.username.data})
        if existing_user:
            flash('Користувач з таким логіном вже існує.', 'warning')
            return redirect(url_for('register'))
        password_hash = generate_password_hash(form.password.data)
        new_user = {
            'username': form.username.data,
            'password': password_hash,
            'role': form.role.data
        }
        db.users.insert_one(new_user)
        flash('Реєстрація успішна! Тепер ви можете увійти в систему.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


# Форма відновлення пароля
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    # Зауваження: Відображення паролів є небезпечним і не рекомендується.
    # Краще реалізувати механізм скидання пароля через електронну пошту або секретне питання.
    flash('Функція відновлення пароля наразі недоступна. Зверніться до адміністратора.', 'warning')
    return redirect(url_for('login'))


# Сторінка доступу заборонена
@app.route('/access_denied')
def access_denied():
    return render_template('access_denied.html')


# Управління користувачами
@app.route('/users')
@login_required
def user_management():
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    users = list(db.users.find())
    return render_template('user_management.html', users=users)


@app.route('/users/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    user_data = db.users.find_one({'_id': ObjectId(user_id)})
    if not user_data:
        flash('Користувача не знайдено.', 'danger')
        return redirect(url_for('user_management'))
    form = RegisterForm(data={
        'username': user_data['username'],
        'role': user_data['role']
    })
    if form.validate_on_submit():
        update_data = {
            'username': form.username.data,
            'role': form.role.data
        }
        if form.password.data:
            update_data['password'] = generate_password_hash(form.password.data)
        db.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
        flash('Користувача успішно оновлено.', 'success')
        return redirect(url_for('user_management'))
    return render_template('register.html', form=form, form_type='edit')


@app.route('/users/delete/<user_id>')
@login_required
def delete_user(user_id):
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    if str(current_user.id) == user_id:
        flash('Ви не можете видалити свій власний акаунт.', 'danger')
        return redirect(url_for('user_management'))
    db.users.delete_one({'_id': ObjectId(user_id)})
    flash('Користувача видалено.', 'success')
    return redirect(url_for('user_management'))


# Маршрути для торговельних точок
@app.route('/trade_points')
@login_required
def trade_points():
    trade_points = list(db.trade_points.find())
    return render_template('trade_points/trade_points.html', trade_points=trade_points)


@app.route('/supplier_orders/receive_list')
@login_required
def supplier_orders_receive_list():
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    # Отримуємо список замовлень, які ще не були отримані
    supplier_orders = list(db.supplier_orders.find({'received': {'$ne': True}}))
    # Додаємо інформацію про постачальника
    for order in supplier_orders:
        supplier = db.suppliers.find_one({'_id': ObjectId(order['supplier_id'])})
        order['supplier_name'] = supplier['name'] if supplier else 'Невідомий постачальник'
    return render_template('supplier_orders/receive_list.html', supplier_orders=supplier_orders)

@app.route('/trade_points/add', methods=['GET', 'POST'])
@login_required
def add_trade_point():
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = TradePointForm()
    if form.validate_on_submit():
        trade_point = {
            'name': form.name.data,
            'type': form.type.data,
            'size': form.size.data,
            'rent_payments': form.rent_payments.data,
            'utility_payments': form.utility_payments.data,
            'number_of_counters': form.number_of_counters.data,
            'halls': [hall.strip() for hall in form.halls.data.split(',')] if form.halls.data else [],
            'sections': [section.strip() for section in form.sections.data.split(',')] if form.sections.data else [],
            'sellers': [],
            'products': []
        }
        db.trade_points.insert_one(trade_point)
        flash('Торговельну точку успішно додано.', 'success')
        return redirect(url_for('trade_points'))
    return render_template('trade_points/trade_point_form.html', form=form, form_type='add')


@app.route('/trade_points/edit/<trade_point_id>', methods=['GET', 'POST'])
@login_required
def edit_trade_point(trade_point_id):
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    trade_point = db.trade_points.find_one({'_id': ObjectId(trade_point_id)})
    if not trade_point:
        flash('Торговельну точку не знайдено.', 'danger')
        return redirect(url_for('trade_points'))
    form = TradePointForm(data={
        'name': trade_point['name'],
        'type': trade_point['type'],
        'size': trade_point['size'],
        'rent_payments': trade_point['rent_payments'],
        'utility_payments': trade_point['utility_payments'],
        'number_of_counters': trade_point['number_of_counters'],
        'halls': ', '.join(trade_point.get('halls', [])),
        'sections': ', '.join(trade_point.get('sections', []))
    })
    if form.validate_on_submit():
        updated_data = {
            'name': form.name.data,
            'type': form.type.data,
            'size': form.size.data,
            'rent_payments': form.rent_payments.data,
            'utility_payments': form.utility_payments.data,
            'number_of_counters': form.number_of_counters.data,
            'halls': [hall.strip() for hall in form.halls.data.split(',')] if form.halls.data else [],
            'sections': [section.strip() for section in form.sections.data.split(',')] if form.sections.data else []
        }
        db.trade_points.update_one({'_id': ObjectId(trade_point_id)}, {'$set': updated_data})
        flash('Торговельну точку успішно оновлено.', 'success')
        return redirect(url_for('trade_points'))
    return render_template('trade_points/trade_point_form.html', form=form, form_type='edit')


@app.route('/trade_points/delete/<trade_point_id>')
@login_required
def delete_trade_point(trade_point_id):
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    db.trade_points.delete_one({'_id': ObjectId(trade_point_id)})
    flash('Торговельну точку видалено.', 'success')
    return redirect(url_for('trade_points'))


# Маршрути для продавців
@app.route('/sellers')
@login_required
def sellers():
    sellers = list(db.sellers.find())
    # Додати ім'я торговельної точки до кожного продавця
    for seller in sellers:
        trade_point = db.trade_points.find_one({'_id': ObjectId(seller['trade_point_id'])})
        seller['trade_point_name'] = trade_point['name'] if trade_point else 'Не вказано'
    return render_template('sellers/sellers.html', sellers=sellers)


@app.route('/sellers/<seller_id>')
@login_required
def view_seller(seller_id):
    seller = db.sellers.find_one({'_id': ObjectId(seller_id)})
    if not seller:
        flash('Продавця не знайдено.', 'danger')
        return redirect(url_for('sellers'))
    trade_point = db.trade_points.find_one({'_id': ObjectId(seller['trade_point_id'])})
    seller['trade_point_name'] = trade_point['name'] if trade_point else 'Не вказано'
    return render_template('sellers/seller_detail.html', seller=seller)


@app.route('/sellers/add', methods=['GET', 'POST'])
@login_required
def add_seller():
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = SellerForm()
    # Заповнити вибір торговельних точок
    trade_points = list(db.trade_points.find())
    form.trade_point_id.choices = [(str(tp['_id']), tp['name']) for tp in trade_points]
    if form.validate_on_submit():
        seller = {
            'name': form.name.data,
            'trade_point_id': form.trade_point_id.data,
            'salary': form.salary.data
        }
        db.sellers.insert_one(seller)
        # Додати продавця до торговельної точки
        db.trade_points.update_one({'_id': ObjectId(form.trade_point_id.data)}, {'$push': {'sellers': seller['_id']}})
        flash('Продавця успішно додано.', 'success')
        return redirect(url_for('sellers'))
    return render_template('sellers/seller_form.html', form=form, form_type='add')


@app.route('/sellers/edit/<seller_id>', methods=['GET', 'POST'])
@login_required
def edit_seller(seller_id):
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    seller = db.sellers.find_one({'_id': ObjectId(seller_id)})
    if not seller:
        flash('Продавця не знайдено.', 'danger')
        return redirect(url_for('sellers'))
    form = SellerForm(data={
        'name': seller['name'],
        'trade_point_id': seller['trade_point_id'],
        'salary': seller['salary']
    })
    # Заповнити вибір торговельних точок
    trade_points = list(db.trade_points.find())
    form.trade_point_id.choices = [(str(tp['_id']), tp['name']) for tp in trade_points]
    if form.validate_on_submit():
        # Якщо торговельна точка змінилася, оновити посилання
        if form.trade_point_id.data != seller['trade_point_id']:
            # Видалити продавця з попередньої торговельної точки
            db.trade_points.update_one({'_id': ObjectId(seller['trade_point_id'])},
                                       {'$pull': {'sellers': seller['_id']}})
            # Додати продавця до нової торговельної точки
            db.trade_points.update_one({'_id': ObjectId(form.trade_point_id.data)},
                                       {'$push': {'sellers': seller['_id']}})
        updated_data = {
            'name': form.name.data,
            'trade_point_id': form.trade_point_id.data,
            'salary': form.salary.data
        }
        db.sellers.update_one({'_id': ObjectId(seller_id)}, {'$set': updated_data})
        flash('Продавця успішно оновлено.', 'success')
        return redirect(url_for('sellers'))
    return render_template('sellers/seller_form.html', form=form, form_type='edit')


@app.route('/sellers/delete/<seller_id>')
@login_required
def delete_seller(seller_id):
    if current_user.role not in ['owner', 'admin']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    seller = db.sellers.find_one({'_id': ObjectId(seller_id)})
    if not seller:
        flash('Продавця не знайдено.', 'danger')
        return redirect(url_for('sellers'))
    # Видалити продавця з торговельної точки
    db.trade_points.update_one({'_id': ObjectId(seller['trade_point_id'])}, {'$pull': {'sellers': seller['_id']}})
    db.sellers.delete_one({'_id': ObjectId(seller_id)})
    flash('Продавця видалено.', 'success')
    return redirect(url_for('sellers'))


# Маршрути для товарів
@app.route('/products')
@login_required
def products():
    products = list(db.products.find())
    # Додати імена постачальників до кожного товару
    for product in products:
        suppliers = list(db.suppliers.find({'_id': {'$in': [ObjectId(sid) for sid in product.get('suppliers', [])]}}))
        product['supplier_names'] = [supplier['name'] for supplier in suppliers]
    return render_template('products/products.html', products=products)


@app.route('/products/<product_id>')
@login_required
def view_product(product_id):
    product = db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash('Товар не знайдено.', 'danger')
        return redirect(url_for('products'))
    # Отримати постачальників
    suppliers = list(db.suppliers.find({'_id': {'$in': [ObjectId(sid) for sid in product.get('suppliers', [])]}}))
    # Отримати ціни в торговельних точках
    prices = []
    for price_info in product.get('prices', []):
        trade_point = db.trade_points.find_one({'_id': ObjectId(price_info['trade_point_id'])})
        prices.append({
            'trade_point_name': trade_point['name'] if trade_point else 'Не вказано',
            'amount': price_info['price']
        })
    return render_template('products/product_detail.html', product=product, suppliers=suppliers, prices=prices)


@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = ProductForm()
    # Заповнити вибір постачальників
    suppliers = list(db.suppliers.find())
    form.suppliers.choices = [(str(supplier['_id']), supplier['name']) for supplier in suppliers]
    if form.validate_on_submit():
        product = {
            'name': form.name.data,
            'description': form.description.data,
            'suppliers': [form.suppliers.data],
            'prices': []  # Можливо, додати логіку для цін
        }
        db.products.insert_one(product)
        flash('Товар успішно додано.', 'success')
        return redirect(url_for('products'))
    return render_template('products/product_form.html', form=form, form_type='add')


@app.route('/products/edit/<product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    product = db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash('Товар не знайдено.', 'danger')
        return redirect(url_for('products'))
    form = ProductForm(data={
        'name': product['name'],
        'description': product.get('description', ''),
        'suppliers': product.get('suppliers', [])[0] if product.get('suppliers') else ''
    })
    # Заповнити вибір постачальників
    suppliers = list(db.suppliers.find())
    form.suppliers.choices = [(str(supplier['_id']), supplier['name']) for supplier in suppliers]
    if form.validate_on_submit():
        updated_data = {
            'name': form.name.data,
            'description': form.description.data,
            'suppliers': [form.suppliers.data]
            # Можливо, додати логіку для оновлення цін
        }
        db.products.update_one({'_id': ObjectId(product_id)}, {'$set': updated_data})
        flash('Товар успішно оновлено.', 'success')
        return redirect(url_for('products'))
    return render_template('products/product_form.html', form=form, form_type='edit')


@app.route('/products/delete/<product_id>')
@login_required
def delete_product(product_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    db.products.delete_one({'_id': ObjectId(product_id)})
    flash('Товар видалено.', 'success')
    return redirect(url_for('products'))


# Маршрути для постачальників
@app.route('/suppliers')
@login_required
def suppliers():
    suppliers = list(db.suppliers.find())
    return render_template('suppliers/suppliers.html', suppliers=suppliers)


@app.route('/suppliers/<supplier_id>')
@login_required
def view_supplier(supplier_id):
    supplier = db.suppliers.find_one({'_id': ObjectId(supplier_id)})
    if not supplier:
        flash('Постачальника не знайдено.', 'danger')
        return redirect(url_for('suppliers'))
    # Отримати товари, які постачає постачальник
    products = list(db.products.find({'suppliers': supplier_id}))
    return render_template('suppliers/supplier_detail.html', supplier=supplier, products=products)


@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = {
            'name': form.name.data,
            'contact_info': form.contact_info.data
        }
        db.suppliers.insert_one(supplier)
        flash('Постачальника успішно додано.', 'success')
        return redirect(url_for('suppliers'))
    return render_template('suppliers/supplier_form.html', form=form, form_type='add')


@app.route('/suppliers/edit/<supplier_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    supplier = db.suppliers.find_one({'_id': ObjectId(supplier_id)})
    if not supplier:
        flash('Постачальника не знайдено.', 'danger')
        return redirect(url_for('suppliers'))
    form = SupplierForm(data={
        'name': supplier['name'],
        'contact_info': supplier['contact_info']
    })
    if form.validate_on_submit():
        updated_data = {
            'name': form.name.data,
            'contact_info': form.contact_info.data
        }
        db.suppliers.update_one({'_id': ObjectId(supplier_id)}, {'$set': updated_data})
        flash('Постачальника успішно оновлено.', 'success')
        return redirect(url_for('suppliers'))
    return render_template('suppliers/supplier_form.html', form=form, form_type='edit')


@app.route('/suppliers/delete/<supplier_id>')
@login_required
def delete_supplier(supplier_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    db.suppliers.delete_one({'_id': ObjectId(supplier_id)})
    flash('Постачальника видалено.', 'success')
    return redirect(url_for('suppliers'))


# Маршрути для замовлень постачальникам
@app.route('/supplier_orders')
@login_required
def supplier_orders():
    orders = list(db.supplier_orders.find())
    for order in orders:
        supplier = db.suppliers.find_one({'_id': ObjectId(order['supplier_id'])})
        order['supplier_name'] = supplier['name'] if supplier else 'Не вказано'
    return render_template('supplier_orders/supplier_orders.html', supplier_orders=orders)


@app.route('/supplier_orders/<order_id>')
@login_required
def view_supplier_order(order_id):
    order = db.supplier_orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        flash('Замовлення не знайдено.', 'danger')
        return redirect(url_for('supplier_orders'))
    supplier = db.suppliers.find_one({'_id': ObjectId(order['supplier_id'])})
    order['supplier_name'] = supplier['name'] if supplier else 'Не вказано'
    # Отримати назви товарів
    products_ordered = []
    for item in order.get('products_ordered', []):
        product = db.products.find_one({'_id': ObjectId(item['product_id'])})
        products_ordered.append({
            'product_name': product['name'] if product else 'Не вказано',
            'quantity': item['quantity']
        })
    return render_template('supplier_orders/supplier_order_detail.html', order=order, products_ordered=products_ordered)



@app.route('/supplier_orders/edit/<order_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier_order(order_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    order = db.supplier_orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        flash('Замовлення не знайдено.', 'danger')
        return redirect(url_for('supplier_orders'))
    form = SupplierOrderForm()
    # Заповнити вибір постачальників
    suppliers = list(db.suppliers.find())
    form.supplier_id.choices = [(str(supplier['_id']), supplier['name']) for supplier in suppliers]
    # Заповнити вибір товарів
    products = list(db.products.find())
    product_choices = [(str(product['_id']), product['name']) for product in products]
    if request.method == 'GET':
        form.supplier_id.data = order['supplier_id']
        form.order_date.data = order['order_date']
        form.products_ordered.entries = []
        for item in order.get('products_ordered', []):
            item_form = SupplierOrderItemForm()
            item_form.product_id.choices = product_choices
            item_form.product_id.data = item['product_id']
            item_form.quantity.data = item['quantity']
            form.products_ordered.append_entry(item_form.data)
    else:
        for item_form in form.products_ordered:
            item_form.product_id.choices = product_choices
    if form.validate_on_submit():
        products_ordered = []
        for item in form.products_ordered.entries:
            products_ordered.append({
                'product_id': item.form.product_id.data,
                'quantity': item.form.quantity.data
            })
        updated_data = {
            'supplier_id': form.supplier_id.data,
            'order_date': form.order_date.data,
            'products_ordered': products_ordered
        }
        db.supplier_orders.update_one({'_id': ObjectId(order_id)}, {'$set': updated_data})
        flash('Замовлення успішно оновлено.', 'success')
        return redirect(url_for('supplier_orders'))
    return render_template('supplier_orders/supplier_order_form.html', form=form, form_type='edit')


@app.route('/supplier_orders/delete/<order_id>')
@login_required
def delete_supplier_order(order_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    db.supplier_orders.delete_one({'_id': ObjectId(order_id)})
    flash('Замовлення видалено.', 'success')
    return redirect(url_for('supplier_orders'))


class SalesFilterForm(FlaskForm):
    trade_point_id = SelectField('Торговельна точка', choices=[], validators=[Optional()], coerce=str)
    seller_id = SelectField('Продавець', choices=[], validators=[Optional()], coerce=str)
    submit = SubmitField('Фільтрувати')


# Маршрути для продажів
@app.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():

    filter_form = SalesFilterForm(request.args)

    # Заповнюємо вибір торговельних точок
    trade_points = list(db.trade_points.find())
    filter_form.trade_point_id.choices = [('', 'Всі торговельні точки')] + [(str(tp['_id']), tp['name']) for tp in
                                                                            trade_points]

    # Заповнюємо вибір продавців
    sellers = list(db.sellers.find())
    filter_form.seller_id.choices = [('', 'Всі продавці')] + [(str(seller['_id']), seller['name']) for seller in
                                                              sellers]

    # Формуємо запит до бази даних з урахуванням фільтрів
    query = {}
    if filter_form.validate():
        if filter_form.trade_point_id.data:
            query['trade_point_id'] = filter_form.trade_point_id.data
        if filter_form.seller_id.data:
            query['seller_id'] = filter_form.seller_id.data

    sales = list(db.sales.find(query))

    # Додаємо додаткову інформацію про продажі
    for sale in sales:
        seller = db.sellers.find_one({'_id': ObjectId(sale['seller_id'])})
        sale['seller_name'] = seller['name'] if seller else 'Не вказано'
        trade_point = db.trade_points.find_one({'_id': ObjectId(sale['trade_point_id'])})
        sale['trade_point_name'] = trade_point['name'] if trade_point else 'Не вказано'
        product = db.products.find_one({'_id': ObjectId(sale['product_id'])})
        sale['product_name'] = product['name'] if product else 'Не вказано'
        if 'customer_id' in sale and sale['customer_id']:
            customer = db.customers.find_one({'_id': ObjectId(sale['customer_id'])})
            sale['customer_name'] = customer['name'] if customer else 'Не вказано'

    return render_template('sales/sales.html', sales=sales, filter_form=filter_form)


@app.route('/sales/<sale_id>')
@login_required
def view_sale(sale_id):
    sale = db.sales.find_one({'_id': ObjectId(sale_id)})
    if not sale:
        flash('Продаж не знайдено.', 'danger')
        return redirect(url_for('sales'))
    seller = db.sellers.find_one({'_id': ObjectId(sale['seller_id'])})
    trade_point = db.trade_points.find_one({'_id': ObjectId(sale['trade_point_id'])})
    product = db.products.find_one({'_id': ObjectId(sale['product_id'])})
    customer = db.customers.find_one({'_id': ObjectId(sale['customer_id'])}) if sale.get('customer_id') else None
    sale_details = {
        'seller_name': seller['name'] if seller else 'Не вказано',
        'trade_point_name': trade_point['name'] if trade_point else 'Не вказано',
        'product_name': product['name'] if product else 'Не вказано',
        'customer_name': customer['name'] if customer else None,
        'quantity': sale['quantity'],
        'price': sale['price'],
        'date': sale['date']
    }
    return render_template('sales/sale_detail.html', sale=sale_details)


@app.route('/sales/add', methods=['GET', 'POST'])
@login_required
def add_sale():
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = SaleForm()
    # Заповнити вибір торговельних точок
    trade_points = list(db.trade_points.find())
    form.trade_point_id.choices = [(str(tp['_id']), tp['name']) for tp in trade_points]
    # Заповнити вибір продавців (можна фільтрувати за торговельною точкою)
    sellers = list(db.sellers.find())
    form.seller_id.choices = [(str(seller['_id']), seller['name']) for seller in sellers]
    # Заповнити вибір товарів
    products = list(db.products.find())
    form.product_id.choices = [(str(product['_id']), product['name']) for product in products]
    # Заповнити вибір покупців
    customers = list(db.customers.find())
    form.customer_id.choices = [(str(customer['_id']), customer['name']) for customer in customers]
    if form.validate_on_submit():
        sale = {
            'trade_point_id': form.trade_point_id.data,
            'seller_id': form.seller_id.data,
            'product_id': form.product_id.data,
            'quantity': form.quantity.data,
            'price': form.price.data,
            'date': form.date.data,
            'customer_id': form.customer_id.data if form.customer_id.data else None
        }
        db.sales.insert_one(sale)
        flash('Продаж успішно додано.', 'success')
        return redirect(url_for('sales'))
    return render_template('sales/sale_form.html', form=form, form_type='add')


@app.route('/sales/edit/<sale_id>', methods=['GET', 'POST'])
@login_required
def edit_sale(sale_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    sale = db.sales.find_one({'_id': ObjectId(sale_id)})
    if not sale:
        flash('Продаж не знайдено.', 'danger')
        return redirect(url_for('sales'))
    form = SaleForm(data={
        'trade_point_id': sale['trade_point_id'],
        'seller_id': sale['seller_id'],
        'product_id': sale['product_id'],
        'quantity': sale['quantity'],
        'price': sale['price'],
        'date': sale['date'],
        'customer_id': sale.get('customer_id', '')
    })
    # Заповнити вибір торговельних точок
    trade_points = list(db.trade_points.find())
    form.trade_point_id.choices = [(str(tp['_id']), tp['name']) for tp in trade_points]
    # Заповнити вибір продавців
    sellers = list(db.sellers.find())
    form.seller_id.choices = [(str(seller['_id']), seller['name']) for seller in sellers]
    # Заповнити вибір товарів
    products = list(db.products.find())
    form.product_id.choices = [(str(product['_id']), product['name']) for product in products]
    # Заповнити вибір покупців
    customers = list(db.customers.find())
    form.customer_id.choices = [(str(customer['_id']), customer['name']) for customer in customers]
    if form.validate_on_submit():
        updated_data = {
            'trade_point_id': form.trade_point_id.data,
            'seller_id': form.seller_id.data,
            'product_id': form.product_id.data,
            'quantity': form.quantity.data,
            'price': form.price.data,
            'date': form.date.data,
            'customer_id': form.customer_id.data if form.customer_id.data else None
        }
        db.sales.update_one({'_id': ObjectId(sale_id)}, {'$set': updated_data})
        flash('Продаж успішно оновлено.', 'success')
        return redirect(url_for('sales'))
    return render_template('sales/sale_form.html', form=form, form_type='edit')


@app.route('/sales/delete/<sale_id>')
@login_required
def delete_sale(sale_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    db.sales.delete_one({'_id': ObjectId(sale_id)})
    flash('Продаж видалено.', 'success')
    return redirect(url_for('sales'))


# Маршрути для покупців
@app.route('/customers')
@login_required
def customers():
    customers = list(db.customers.find())
    return render_template('customers/customers.html', customers=customers)


@app.route('/customers/<customer_id>')
@login_required
def view_customer(customer_id):
    customer = db.customers.find_one({'_id': ObjectId(customer_id)})
    if not customer:
        flash('Покупця не знайдено.', 'danger')
        return redirect(url_for('customers'))
    # Отримати історію покупок
    sales = list(db.sales.find({'customer_id': customer_id}))
    # Додати інформацію про продажі
    for sale in sales:
        product = db.products.find_one({'_id': ObjectId(sale['product_id'])})
        sale['product_name'] = product['name'] if product else 'Не вказано'
        sale['trade_point_name'] = db.trade_points.find_one({'_id': ObjectId(sale['trade_point_id'])})[
            'name'] if db.trade_points.find_one({'_id': ObjectId(sale['trade_point_id'])}) else 'Не вказано'
        sale['seller_name'] = db.sellers.find_one({'_id': ObjectId(sale['seller_id'])})['name'] if db.sellers.find_one(
            {'_id': ObjectId(sale['seller_id'])}) else 'Не вказано'
    return render_template('customers/customer_detail.html', customer=customer, sales=sales)


@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = CustomerForm()
    if form.validate_on_submit():
        customer = {
            'name': form.name.data,
            'characteristics': form.characteristics.data
        }
        db.customers.insert_one(customer)
        flash('Покупця успішно додано.', 'success')
        return redirect(url_for('customers'))
    return render_template('customers/customer_form.html', form=form, form_type='add')


@app.route('/customers/edit/<customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    customer = db.customers.find_one({'_id': ObjectId(customer_id)})
    if not customer:
        flash('Покупця не знайдено.', 'danger')
        return redirect(url_for('customers'))
    form = CustomerForm(data={
        'name': customer['name'],
        'characteristics': customer.get('characteristics', '')
    })
    if form.validate_on_submit():
        updated_data = {
            'name': form.name.data,
            'characteristics': form.characteristics.data
        }
        db.customers.update_one({'_id': ObjectId(customer_id)}, {'$set': updated_data})
        flash('Покупця успішно оновлено.', 'success')
        return redirect(url_for('customers'))
    return render_template('customers/customer_form.html', form=form, form_type='edit')


@app.route('/customers/delete/<customer_id>')
@login_required
def delete_customer(customer_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    db.customers.delete_one({'_id': ObjectId(customer_id)})
    flash('Покупця видалено.', 'success')
    return redirect(url_for('customers'))


# Маршрути для заявок з торговельних точок
@app.route('/requests')
@login_required
def requests_route():
    requests_list = list(db.requests.find())
    for req in requests_list:
        trade_point = db.trade_points.find_one({'_id': ObjectId(req['trade_point_id'])})
        req['trade_point_name'] = trade_point['name'] if trade_point else 'Не вказано'
    return render_template('requests/requests.html', requests=requests_list)


@app.route('/requests/<request_id>')
@login_required
def view_request(request_id):
    request_item = db.requests.find_one({'_id': ObjectId(request_id)})
    if not request_item:
        flash('Заявку не знайдено.', 'danger')
        return redirect(url_for('list_requests'))

    trade_point = db.trade_points.find_one({'_id': ObjectId(request_item['trade_point_id'])})
    request_item['trade_point_name'] = trade_point['name'] if trade_point else 'Не вказано'

    # Get product names
    products_requested = []
    for item in request_item.get('products_requested', []):
        product_data = db.products.find_one({'_id': ObjectId(item['product_id'])})
        products_requested.append({
            'product_name': product_data['name'] if product_data else 'Не вказано',
            'quantity': item['quantity']
        })

    return render_template('requests/request_detail.html', request=request_item, products_requested=products_requested)



@app.route('/requests/add', methods=['GET', 'POST'])
def add_request():
    if request.method == 'POST':
        # Get data from the form
        date = request.form.get('date')
        trade_point_id = request.form.get('trade_point_id')
        products_requested = []
        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')

        for product_id, quantity in zip(product_ids, quantities):
            products_requested.append({
                'product_id': product_id,
                'quantity': quantity
            })

        # Create new request object
        new_request = {
            'date': date,
            'trade_point_id': trade_point_id,
            'products_requested': products_requested
        }

        # Insert into the database
        db.requests.insert_one(new_request)
        flash('Заявку успішно додано.', 'success')
        return redirect(url_for('add_request'))

    # Get trade points and products from the database
    trade_points = list(db.trade_points.find())
    products = list(db.products.find())

    return render_template('requests/request_form.html', trade_points=trade_points, products=products)


@app.route('/requests/edit/<request_id>', methods=['GET', 'POST'])
@login_required
def edit_request(request_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    request_item = db.requests.find_one({'_id': ObjectId(request_id)})
    if not request_item:
        flash('Заявку не знайдено.', 'danger')
        return redirect(url_for('requests_route'))
    form = RequestForm()
    # Заповнити вибір торговельних точок
    trade_points = list(db.trade_points.find())
    form.trade_point_id.choices = [(str(tp['_id']), tp['name']) for tp in trade_points]
    # Заповнити вибір товарів
    products = list(db.products.find())
    product_choices = [(str(product['_id']), product['name']) for product in products]
    if request.method == 'GET':
        form.trade_point_id.data = request_item['trade_point_id']
        form.date.data = request_item['date']
        form.products_requested.entries = []
        for item in request_item.get('products_requested', []):
            item_form = RequestItemForm()
            item_form.product_id.choices = product_choices
            item_form.product_id.data = item['product_id']
            item_form.quantity.data = item['quantity']
            form.products_requested.append_entry(item_form.data)
    else:
        for item_form in form.products_requested:
            item_form.product_id.choices = product_choices
    if form.validate_on_submit():
        products_requested = []
        for item in form.products_requested.entries:
            products_requested.append({
                'product_id': item.form.product_id.data,
                'quantity': item.form.quantity.data
            })
        updated_data = {
            'trade_point_id': form.trade_point_id.data,
            'date': form.date.data,
            'products_requested': products_requested
        }
        db.requests.update_one({'_id': ObjectId(request_id)}, {'$set': updated_data})
        flash('Заявку успішно оновлено.', 'success')
        return redirect(url_for('requests_route'))
    return render_template('requests/request_form.html', form=form, form_type='edit')


@app.route('/requests/delete/<request_id>')
@login_required
def delete_request(request_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    db.requests.delete_one({'_id': ObjectId(request_id)})
    flash('Заявку видалено.', 'success')
    return redirect(url_for('requests_route'))


# Маршрути для звітів
@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    report_data = None
    if request.method == 'POST':
        report_type = request.form.get('report_type')
        if report_type == '1':
            # Одержати відомості про найбільш активних покупців по всіх торговельних точках
            pipeline = [
                {"$match": {"customer_id": {"$ne": None}}},
                {"$group": {"_id": "$customer_id", "total_purchases": {"$sum": "$quantity"}}},
                {"$sort": {"total_purchases": -1}},
                {"$limit": 10}
            ]
            active_customers = list(db.sales.aggregate(pipeline))
            # Отримати інформацію про покупців
            for customer in active_customers:
                customer_info = db.customers.find_one({'_id': ObjectId(customer['_id'])})
                customer['name'] = customer_info['name'] if customer_info else 'Не вказано'
            report_data = active_customers
            report_title = "Найбільш активні покупці по всіх торговельних точках"
        elif report_type == '2':
            # Додайте інші типи звітів відповідно до вимог
            flash('Цей тип звіту ще не реалізовано.', 'info')
            report_title = None
            report_data = None
        # Реалізуйте інші типи звітів тут
        else:
            flash('Невідомий тип звіту.', 'danger')
            report_title = None
            report_data = None
        return render_template('reports.html', report_data=report_data, report_title=report_title)
    return render_template('reports.html', report_data=report_data)


# Маршрут для профілю користувача
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


class EditProfileForm(FlaskForm):
    username = StringField('Логін', validators=[DataRequired()])
    email = StringField('Електронна пошта', validators=[DataRequired(), Email()])
    first_name = StringField('Ім\'я', validators=[Optional()])
    last_name = StringField('Прізвище', validators=[Optional()])
    submit = SubmitField('Зберегти зміни')


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': {
                'username': form.username.data,
                'email': form.email.data,
                'first_name': form.first_name.data,
                'last_name': form.last_name.data,
                # Додайте інші поля за потреби
            }}
        )
        flash('Ваш профіль було оновлено.', 'success')
        return redirect(url_for('profile'))
    else:
        # Передзаповнення форми поточними даними користувача
        user_data = db.users.find_one({'_id': ObjectId(current_user.id)})
        form.username.data = user_data.get('username', '')
        form.email.data = user_data.get('email', '')
        form.first_name.data = user_data.get('first_name', '')
        form.last_name.data = user_data.get('last_name', '')
        # Передзаповніть інші поля за потреби

    return render_template('edit_profile.html', form=form)



@app.route('/supplier_orders/add', methods=['GET', 'POST'])
@login_required
def add_supplier_order():
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = SupplierOrderForm()
    # Заповнити вибір постачальників
    suppliers = list(db.suppliers.find())
    form.supplier_id.choices = [(str(supplier['_id']), supplier['name']) for supplier in suppliers]
    # Заповнити вибір заявок
    requests = list(db.requests.find())
    form.requests.choices = [(str(request['_id']), f"Заявка {request['_id']} від {request['date']}") for request in
                             requests]
    if form.validate_on_submit():
        selected_requests = form.requests.data
        products_ordered = []
        for request_id in selected_requests:
            request = db.requests.find_one({'_id': ObjectId(request_id)})
            for item in request['products_requested']:
                product = db.products.find_one({'_id': ObjectId(item['product_id'])})
                if not product:
                    # Додати новий товар до довідника
                    new_product = {
                        '_id': ObjectId(item['product_id']),
                        'name': 'Новий товар',
                        'description': '',
                        'suppliers': [form.supplier_id.data]
                    }
                    db.products.insert_one(new_product)
                # Менеджер може змінити кількість товару
                products_ordered.append({
                    'product_id': item['product_id'],
                    'quantity': item['quantity']  # Тут можна додати можливість змінювати кількість
                })
        order = {
            'supplier_id': form.supplier_id.data,
            'order_date': form.order_date.data,
            'products_ordered': products_ordered,
            'requests': selected_requests
        }
        db.supplier_orders.insert_one(order)
        flash('Замовлення успішно додано.', 'success')
        return redirect(url_for('supplier_orders'))
    return render_template('supplier_order_form.html', form=form, form_type='add')

@app.route('/supplier_orders/receive/<supplier_order_id>', methods=['GET', 'POST'])
@login_required
def receive_supplier_order(supplier_order_id):
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    supplier_order = db.supplier_orders.find_one({'_id': ObjectId(supplier_order_id)})
    if not supplier_order:
        flash('Замовлення не знайдено.', 'danger')
        return redirect(url_for('supplier_orders'))
    # Розподіл товару по торговельних точках на основі заявок
    for request_id in supplier_order['related_requests']:
        request_item = db.requests.find_one({'_id': ObjectId(request_id)})
        trade_point_id = request_item['trade_point_id']
        for product_request in request_item.get('products_requested', []):
            product_id = product_request['product_id']
            quantity = product_request['quantity']
            # Оновити запаси товару в торговельній точці
            db.trade_points.update_one(
                {'_id': ObjectId(trade_point_id)},
                {'$inc': {f'inventory.{product_id}': quantity}}
            )
    flash('Товар успішно отримано та розподілено по торговельних точках.', 'success')
    return redirect(url_for('supplier_orders'))


class SaleForm(FlaskForm):
    trade_point_id = SelectField('Trade Point', validators=[DataRequired()])
    seller_id = SelectField('Seller', validators=[DataRequired()])
    product_id = SelectField('Product', validators=[DataRequired()])
    customer_id = SelectField('Customer', choices=[], validators=[])
    quantity = IntegerField('Quantity', validators=[DataRequired()])
    price = DecimalField('Price', validators=[DataRequired()])
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Зберегти')


@app.route('/sales/create', methods=['GET', 'POST'])
@login_required
def create_sale():
    # Access Control
    if current_user.role not in ['owner', 'admin', 'operator', 'seller']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))

    form = SaleForm()

    # Populate Trade Points Choices
    trade_points = list(db.trade_points.find())
    form.trade_point_id.choices = [(str(tp['_id']), tp['name']) for tp in trade_points]

    # Populate Sellers Choices
    sellers = list(db.sellers.find())
    form.seller_id.choices = [(str(seller['_id']), seller['name']) for seller in sellers]

    # Populate Products Choices
    products = list(db.products.find())
    form.product_id.choices = [(str(product['_id']), product['name']) for product in products]

    # Populate Customers Choices
    customers = list(db.customers.find())
    form.customer_id.choices = [('', 'Невідомий')] + [(str(customer['_id']), customer['name']) for customer in customers]

    if form.validate_on_submit():
        try:
            try:
                trade_point_id = ObjectId(form.trade_point_id.data)
                seller_id = ObjectId(form.seller_id.data)
                product_id = ObjectId(form.product_id.data)
                customer_id = ObjectId(form.customer_id.data) if form.customer_id.data else None
            except InvalidId:
                flash('Невірний формат ідентифікатора.', 'danger')
                return redirect(url_for('create_sale'))

            # Fetch the selected Trade Point
            trade_point = db.trade_points.find_one({'_id': trade_point_id})
            if not trade_point:
                flash('Торговельна точка не знайдена.', 'danger')
                return redirect(url_for('create_sale'))

            # Determine Customer ID based on Trade Point Type
            if trade_point.get('type') in ['Кіоск', 'Лоток']:
                customer_id = None  # Do not record customer for kiosks and stalls
            else:
                # Optional: Validate if the customer exists
                if customer_id:
                    customer = db.customers.find_one({'_id': customer_id})
                    if not customer:
                        flash('Клієнт не знайдений.', 'danger')
                        return redirect(url_for('create_sale'))
                else:
                    customer_id = None

            # Prepare the sale document
            sale = {
                'trade_point_id': trade_point_id,
                'seller_id': seller_id,
                'product_id': product_id,
                'quantity': form.quantity.data,
                'price': float(form.price.data),  # Ensure price is stored as a float
                'customer_id': customer_id
            }

            # Update Product Inventory in the Trade Point
            update_result = db.trade_points.update_one(
                {'_id': trade_point_id},
                {'$inc': {f'inventory.{str(product_id)}': -form.quantity.data}}
            )

            if update_result.modified_count == 0:
                flash('Не вдалося оновити залишки товару.', 'warning')
                return redirect(url_for('create_sale'))

            # Insert the Sale Document into MongoDB
            db.sales.insert_one(sale)

            flash('Продаж успішно додано.', 'success')
            return redirect(url_for('sales'))

        except Exception as e:
            # Log the exception (configure logging as needed)
            app.logger.error(f"Error creating sale: {e}")
            flash('Сталася помилка при додаванні продажу.', 'danger')
            return redirect(url_for('create_sale'))

    return render_template('sales/sale_form.html', form=form, form_type='add')


@app.route('/trade_points/view/<trade_point_id>')
@login_required
def view_trade_point(trade_point_id):
    trade_point = db.trade_points.find_one({'_id': ObjectId(trade_point_id)})
    if not trade_point:
        flash('Торговельну точку не знайдено.', 'danger')
        return redirect(url_for('trade_points'))
    # Отримати інформацію про залишки товару
    inventory = []
    for product_id_str, quantity in trade_point.get('inventory', {}).items():
        product = db.products.find_one({'_id': ObjectId(product_id_str)})
        inventory.append({
            'product_name': product['name'] if product else 'Невідомий товар',
            'quantity': quantity
        })
    return render_template('trade_points/trade_point_detail.html', trade_point=trade_point, inventory=inventory)


@app.route('/supplier_orders/create', methods=['GET', 'POST'])
@login_required
def create_supplier_order():
    if current_user.role not in ['owner', 'admin', 'operator']:
        flash('У вас немає прав доступу до цієї сторінки.', 'danger')
        return redirect(url_for('access_denied'))
    form = SupplierOrderForm()
    # Заповнення вибору постачальників
    suppliers = list(db.suppliers.find())
    form.supplier_id.choices = [(str(supplier['_id']), supplier['name']) for supplier in suppliers]
    # Заповнення вибору заявок
    pending_requests = list(db.requests.find())
    form.selected_requests.choices = [(str(request['_id']), f"Заявка {request['_id']} від {request['date']}") for request in pending_requests]
    if request.method == 'POST':
        # Заповнення даних товарів на основі вибраних заявок
        if form.products_ordered.entries == []:
            selected_request_ids = form.selected_requests.data
            for request_id in selected_request_ids:
                request_item = db.requests.find_one({'_id': ObjectId(request_id)})
                for product_request in request_item['products_requested']:
                    product = db.products.find_one({'_id': ObjectId(product_request['product_id'])})
                    if not product:
                        # Додати новий товар до довідника
                        new_product = {
                            '_id': ObjectId(product_request['product_id']),
                            'name': product_request.get('product_name', 'Новий товар'),
                            'description': '',
                            'suppliers': [form.supplier_id.data]
                        }
                        db.products.insert_one(new_product)
                        product = new_product
                    # Додати товар до списку замовлення
                    item_form = SupplierOrderItemForm()
                    item_form.product_id.data = str(product['_id'])
                    item_form.product_name.data = product['name']
                    item_form.quantity.data = product_request['quantity']
                    form.products_ordered.append_entry(item_form.data)
            return render_template('supplier_orders/supplier_order_form.html', form=form, form_type='add')
        else:
            if form.validate_on_submit():
                products_ordered = []
                for item_form in form.products_ordered.entries:
                    products_ordered.append({
                        'product_id': item_form.form.product_id.data,
                        'product_name': item_form.form.product_name.data,
                        'quantity': item_form.form.quantity.data
                    })
                supplier_order = {
                    'supplier_id': form.supplier_id.data,
                    'order_date': form.order_date.data,
                    'products_ordered': products_ordered,
                    'related_requests': form.selected_requests.data
                }
                db.supplier_orders.insert_one(supplier_order)
                flash('Замовлення постачальнику успішно створено.', 'success')
                return redirect(url_for('supplier_orders'))
    return render_template('supplier_orders/supplier_order_form.html', form=form, form_type='add')

# Обробка помилок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_message='Сторінку не знайдено.'), 404



@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_message='Внутрішня помилка сервера.'), 500


# Запуск додатку
if __name__ == '__main__':
    app.run(debug=True)
