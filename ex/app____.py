# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///perfume_shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    orders = db.relationship('Order', backref='customer', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    perfumes = db.relationship('Perfume', backref='category', lazy=True)

class Perfume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    order_items = db.relationship('OrderItem', backref='perfume', lazy=True)
    
    # Additional fields for perfume-specific details
    volume = db.Column(db.String(20))  # e.g., "50ml", "100ml"
    concentration = db.Column(db.String(50))  # e.g., "Eau de Parfum", "Eau de Toilette"
    notes = db.Column(db.Text)  # Description of fragrance notes

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_ordered = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, shipped, delivered, cancelled
    total_amount = db.Column(db.Float, nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    perfume_id = db.Column(db.Integer, db.ForeignKey('perfume.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)  # Price at time of purchase

# Routes
@app.route('/')
def home():
    featured_perfumes = Perfume.query.limit(6).all()
    categories = Category.query.all()
    return render_template('index.html', featured_perfumes=featured_perfumes, categories=categories)

@app.route('/shop')
def shop():
    category_id = request.args.get('category', type=int)
    search_query = request.args.get('search', '')
    
    query = Perfume.query
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if search_query:
        query = query.filter(Perfume.name.contains(search_query) | 
                            Perfume.brand.contains(search_query) | 
                            Perfume.description.contains(search_query))
    
    perfumes = query.all()
    categories = Category.query.all()
    
    return render_template('shop.html', perfumes=perfumes, categories=categories, 
                          selected_category=category_id, search_query=search_query)

@app.route('/perfume/<int:id>')
def perfume_detail(id):
    perfume = Perfume.query.get_or_404(id)
    related_perfumes = Perfume.query.filter_by(category_id=perfume.category_id).filter(Perfume.id != id).limit(4).all()
    return render_template('perfume_detail.html', perfume=perfume, related_perfumes=related_perfumes)

@app.route('/add_to_cart/<int:perfume_id>', methods=['POST'])
def add_to_cart(perfume_id):
    if 'cart' not in session:
        session['cart'] = {}
    
    quantity = int(request.form.get('quantity', 1))
    
    if str(perfume_id) in session['cart']:
        session['cart'][str(perfume_id)] += quantity
    else:
        session['cart'][str(perfume_id)] = quantity
    
    session.modified = True
    flash('Item added to your cart!', 'success')
    return redirect(request.referrer or url_for('shop'))

@app.route('/cart')
def view_cart():
    if 'cart' not in session or not session['cart']:
        return render_template('cart.html', cart_items=None, total=0)
    
    cart_items = []
    total = 0
    
    for perfume_id, quantity in session['cart'].items():
        perfume = Perfume.query.get(int(perfume_id))
        if perfume:
            item_total = perfume.price * quantity
            cart_items.append({
                'perfume': perfume,
                'quantity': quantity,
                'item_total': item_total
            })
            total += item_total
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/update_cart/<int:perfume_id>', methods=['POST'])
def update_cart(perfume_id):
    if 'cart' not in session:
        return redirect(url_for('view_cart'))
    
    quantity = int(request.form.get('quantity', 0))
    
    if quantity > 0:
        session['cart'][str(perfume_id)] = quantity
    else:
        session['cart'].pop(str(perfume_id), None)
    
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please login to checkout', 'warning')
        return redirect(url_for('login'))
    
    if 'cart' not in session or not session['cart']:
        return redirect(url_for('shop'))
    
    if request.method == 'POST':
        # Process order
        user_id = session['user_id']
        shipping_address = request.form.get('address')
        
        # Calculate total
        total = 0
        cart_items = []
        
        for perfume_id, quantity in session['cart'].items():
            perfume = Perfume.query.get(int(perfume_id))
            if perfume and perfume.stock >= quantity:
                item_total = perfume.price * quantity
                cart_items.append({
                    'perfume': perfume,
                    'quantity': quantity,
                    'price': perfume.price
                })
                total += item_total
            else:
                flash(f'Sorry, {perfume.name} is out of stock or has insufficient stock!', 'danger')
                return redirect(url_for('view_cart'))
        
        # Create order
        order = Order(user_id=user_id, total_amount=total, shipping_address=shipping_address)
        db.session.add(order)
        db.session.flush()  # To get the order ID
        
        # Create order items and update stock
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                perfume_id=item['perfume'].id,
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)
            
            # Update stock
            item['perfume'].stock -= item['quantity']
        
        db.session.commit()
        
        # Clear cart
        session.pop('cart', None)
        
        flash('Order placed successfully!', 'success')
        return redirect(url_for('order_confirmation', order_id=order.id))
    
    return render_template('checkout.html')

@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    return render_template('order_confirmation.html', order=order)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username or email already exists
        user_exists = User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first()
        
        if user_exists:
            flash('Username or email already exists!', 'danger')
        else:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out!', 'info')
    return redirect(url_for('home'))

@app.route('/account')
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.date_ordered.desc()).all()
    
    return render_template('account.html', user=user, orders=orders)

# Admin routes
@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    recent_orders = Order.query.order_by(Order.date_ordered.desc()).limit(10).all()
    low_stock_perfumes = Perfume.query.filter(Perfume.stock < 10).all()
    
    return render_template('admin/dashboard.html', recent_orders=recent_orders, low_stock_perfumes=low_stock_perfumes)

@app.route('/admin/perfumes')
def admin_perfumes():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    
    perfumes = Perfume.query.all()
    return render_template('admin/perfumes.html', perfumes=perfumes)

@app.route('/admin/perfume/add', methods=['GET', 'POST'])
def admin_add_perfume():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    
    categories = Category.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        image_url = request.form.get('image_url')
        category_id = int(request.form.get('category_id'))
        volume = request.form.get('volume')
        concentration = request.form.get('concentration')
        notes = request.form.get('notes')
        
        new_perfume = Perfume(
            name=name,
            brand=brand,
            description=description,
            price=price,
            stock=stock,
            image_url=image_url,
            category_id=category_id,
            volume=volume,
            concentration=concentration,
            notes=notes
        )
        
        db.session.add(new_perfume)
        db.session.commit()
        
        flash('Perfume added successfully!', 'success')
        return redirect(url_for('admin_perfumes'))
    
    return render_template('admin/add_perfume.html', categories=categories)

@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    
    orders = Order.query.order_by(Order.date_ordered.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/order/<int:id>')
def admin_order_detail(id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    
    order = Order.query.get_or_404(id)
    return render_template('admin/order_detail.html', order=order)

@app.route('/admin/order/update_status/<int:id>', methods=['POST'])
def admin_update_order_status(id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    
    order = Order.query.get_or_404(id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'shipped', 'delivered', 'cancelled']:
        order.status = new_status
        db.session.commit()
        flash('Order status updated successfully!', 'success')
    
    return redirect(url_for('admin_order_detail', id=order.id))

@app.route('/admin/categories')
def admin_categories():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/category/add', methods=['GET', 'POST'])
def admin_add_category():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        new_category = Category(name=name, description=description)
        db.session.add(new_category)
        db.session.commit()
        
        flash('Category added successfully!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/add_category.html')

# Initialize the database
@app.cli.command('init-db')
def init_db_command():
    db.create_all()
    
    # Create admin user if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@perfumeshop.com', is_admin=True)
        admin.set_password('admin123')  # Change this in production!
        db.session.add(admin)
    
    # Create default categories
    categories = [
        {'name': 'Floral', 'description': 'Perfumes with prominent flower notes'},
        {'name': 'Oriental', 'description': 'Warm, spicy and exotic fragrances'},
        {'name': 'Woody', 'description': 'Fragrances with prominent wood notes'},
        {'name': 'Fresh', 'description': 'Light, clean and invigorating scents'}
    ]
    
    for cat_data in categories:
        if not Category.query.filter_by(name=cat_data['name']).first():
            category = Category(**cat_data)
            db.session.add(category)
    
    db.session.commit()
    print('Database initialized!')

# Sample data for development
@app.cli.command('sample-data')
def sample_data_command():
    # Make sure categories exist
    floral = Category.query.filter_by(name='Floral').first()
    oriental = Category.query.filter_by(name='Oriental').first()
    woody = Category.query.filter_by(name='Woody').first()
    fresh = Category.query.filter_by(name='Fresh').first()
    
    if not (floral and oriental and woody and fresh):
        print('Categories not found. Run init-db first!')
        return
    
    # Sample perfumes
    perfumes = [
        {
            'name': 'Rose Elegance',
            'brand': 'Parfum Paris',
            'description': 'A luxurious blend of rose and jasmine',
            'price': 89.99,
            'stock': 25,
            'image_url': '/static/img/perfumes/rose-elegance.jpg',
            'category_id': floral.id,
            'volume': '50ml',
            'concentration': 'Eau de Parfum',
            'notes': 'Top: Bulgarian Rose; Middle: Jasmine, Lily; Base: Sandalwood, Vanilla'
        },
        {
            'name': 'Amber Mystique',
            'brand': 'Oriental Dreams',
            'description': 'Warm amber with exotic spices',
            'price': 75.50,
            'stock': 15,
            'image_url': '/static/img/perfumes/amber-mystique.jpg',
            'category_id': oriental.id,
            'volume': '100ml',
            'concentration': 'Parfum',
            'notes': 'Top: Bergamot, Cinnamon; Middle: Amber, Rose; Base: Vanilla, Musk'
        },
        {
            'name': 'Cedar Forest',
            'brand': 'Nature Scents',
            'description': 'A walk through a cedar forest after rain',
            'price': 65.00,
            'stock': 20,
            'image_url': '/static/img/perfumes/cedar-forest.jpg',
            'category_id': woody.id,
            'volume': '75ml',
            'concentration': 'Eau de Toilette',
            'notes': 'Top: Lemon, Pine; Middle: Cedar, Cypress; Base: Vetiver, Moss'
        },
        {
            'name': 'Ocean Breeze',
            'brand': 'Aqua Fragrances',
            'description': 'Fresh and invigorating like an ocean breeze',
            'price': 55.99,
            'stock': 30,
            'image_url': '/static/img/perfumes/ocean-breeze.jpg',
            'category_id': fresh.id,
            'volume': '100ml',
            'concentration': 'Eau de Cologne',
            'notes': 'Top: Lemon, Bergamot; Middle: Marine notes, Rosemary; Base: Musk, Amber'
        }
    ]
    
    for perfume_data in perfumes:
        if not Perfume.query.filter_by(name=perfume_data['name']).first():
            perfume = Perfume(**perfume_data)
            db.session.add(perfume)
    
    db.session.commit()
    print('Sample data added!')

if __name__ == '__main__':
    app.run(debug=True)