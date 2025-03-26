# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from flask_cors import CORS


app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///perfume_shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(200), nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    wilaya = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    total_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    order = db.relationship('Order', backref=db.backref('items', lazy=True))
    product = db.relationship('Product')

@app.context_processor
def inject_cart_count():
    def get_cart_count():
        cart = session.get('cart', {})
        return sum(item['quantity'] for item in cart.values())
    return dict(get_cart_count=get_cart_count)

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/products')
def products():
    perfumes = Product.query.all()
    return render_template('products.html', perfumes=perfumes)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash('Please login first', 'warning')
        return redirect(url_for('admin_login'))
    
    products = Product.query.all()
    return render_template('admin_dashboard.html', products=products)

@app.route('/admin/add_product', methods=['GET', 'POST'])
def add_product():
    if not session.get('admin_logged_in'):
        flash('Please login first', 'warning')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        new_product = Product(
            name=request.form.get('name'),
            brand=request.form.get('brand'),
            description=request.form.get('description'),
            price=float(request.form.get('price')),
            image_url=request.form.get('image_url')
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_product.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('home'))


@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Initialize cart if it doesn't exist
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    product_id_str = str(product_id)
    
    if product_id_str in cart:
        cart[product_id_str]['quantity'] += 1
    else:
        cart[product_id_str] = {
            'name': product.name,
            'brand': product.brand,
            'price': product.price,
            'image_url': product.image_url,
            'quantity': 1
        }
    
    session['cart'] = cart
    flash(f'{product.name} added to your cart!', 'success')
    return redirect(url_for('view_cart'))

@app.route('/customer_form', methods=['GET', 'POST'])
def customer_form():
    # Get the product that the user wants to add
    product_id = session.get('pending_product_id')
    if not product_id:
        flash('No product selected', 'danger')
        return redirect(url_for('products'))
    
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone_number = request.form.get('phone_number')
        wilaya = request.form.get('wilaya')
        
        # Validate form data
        if not all([first_name, last_name, phone_number, wilaya]):
            flash('All fields are required', 'danger')
            return render_template('customer_form.html', product=product)
        
        # Initialize cart if it doesn't exist
        if 'cart' not in session:
            session['cart'] = {}
        
        # Add product to cart with customer info
        cart = session['cart']
        product_id_str = str(product_id)
        
        if product_id_str in cart:
            cart[product_id_str]['quantity'] += 1
        else:
            cart[product_id_str] = {
                'name': product.name,
                'brand': product.brand,
                'price': product.price,
                'image_url': product.image_url,
                'quantity': 1,
                'customer_info': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone_number': phone_number,
                    'wilaya': wilaya
                }
            }
        
        session['cart'] = cart
        # Clear the pending product
        session.pop('pending_product_id', None)
        
        flash(f'{product.name} added to your cart!', 'success')
        return redirect(url_for('view_cart'))
    
    return render_template('customer_form.html', product=product)

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    return render_template('cart.html', cart=cart, total=total)



@app.route('/update_cart/<product_id>', methods=['POST'])
def update_cart(product_id):
    cart = session.get('cart', {})
    quantity = int(request.form.get('quantity', 1))
    
    if product_id in cart:
        if quantity > 0:
            cart[product_id]['quantity'] = quantity
        else:
            cart.pop(product_id, None)
        
        session['cart'] = cart
    
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    if product_id in cart:
        product_name = cart[product_id]['name']
        cart.pop(product_id)
        session['cart'] = cart
        flash(f'{product_name} removed from your cart.', 'info')
    
    return redirect(url_for('view_cart'))

@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    flash('Your cart has been cleared.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    
    if not cart:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('products'))
    
    if request.method == 'POST':
        # Get customer info from the form
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone_number = request.form.get('phone_number')
        wilaya = request.form.get('wilaya')
        
        # Validate form data
        if not all([first_name, last_name, phone_number, wilaya]):
            flash('All customer fields are required', 'danger')
            return render_template('checkout.html', cart=cart, total=sum(item['price'] * item['quantity'] for item in cart.values()))
        
        # Calculate total amount
        total_amount = sum(item['price'] * item['quantity'] for item in cart.values())
        
        # Create new order
        order = Order(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            wilaya=wilaya,
            total_amount=total_amount
        )
        
        db.session.add(order)
        db.session.flush()  # Flush to get the order ID
        
        # Create order items
        for product_id, item in cart.items():
            order_item = OrderItem(
                order_id=order.id,
                product_id=int(product_id),
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)
        
        # Commit the transaction
        db.session.commit()
        
        # Clear the cart
        session.pop('cart', None)
        
        # Show success message
        flash('Your order has been placed successfully!', 'success')
        return redirect(url_for('order_confirmation', order_id=order.id))
    
    # Calculate total price
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    
    return render_template('customer_form.html', cart=cart, total=total)

@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_confirmation.html', order=order)

@app.route('/admin/orders')
def admin_orders():
    if not session.get('admin_logged_in'):
        flash('Please login first', 'warning')
        return redirect(url_for('admin_login'))
    
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/order/<int:order_id>')
def admin_order_detail(order_id):
    if not session.get('admin_logged_in'):
        flash('Please login first', 'warning')
        return redirect(url_for('admin_login'))
    
    order = Order.query.get_or_404(order_id)
    return render_template('admin_order_detail.html', order=order)

@app.route('/admin/order/<int:order_id>/update_status', methods=['POST'])
def update_order_status(order_id):
    if not session.get('admin_logged_in'):
        flash('Please login first', 'warning')
        return redirect(url_for('admin_login'))
    
    order = Order.query.get_or_404(order_id)
    status = request.form.get('status')
    
    if status in ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']:
        order.status = status
        db.session.commit()
        flash(f'Order status updated to {status}', 'success')
    
    return redirect(url_for('admin_order_detail', order_id=order.id))

@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if not session.get('admin_logged_in'):
        flash('Please login first', 'warning')
        return redirect(url_for('admin_login'))
    
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if not session.get('admin_logged_in'):
        flash('Please login first', 'warning')
        return redirect(url_for('admin_login'))
    
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.brand = request.form.get('brand')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.image_url = request.form.get('image_url')
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_product.html', product=product)

@app.cli.command('init-db')
def init_db():
    db.create_all()
    
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin')
        admin.set_password('admin123')
        db.session.add(admin)
    
    if not Product.query.first():
        sample_products = [
            Product(
                name='amine No. 5',
                brand='Chanel',
                description='A classic floral fragrance with notes of rose and jasmine.',
                price=160.00,
                image_url='/static/img/chanel_no5.jpg'
            ),
            Product(
                name='Dior Sauvage',
                brand='Dior',
                description='A fresh and spicy masculine fragrance with notes of bergamot and pepper.',
                price=95.00,
                image_url='https://i.ibb.co/MxZKhzCh/images.jpg'
            ),
            Product(
                name='Flowerbomb',
                brand='Viktor & Rolf',
                description='An explosive floral fragrance with notes of jasmine, rose, and patchouli.',
                price=85.00,
                image_url='https://i.ibb.co/MxZKhzCh/images.jpg'
            )
        ]
        db.session.add_all(sample_products)
        
    db.session.commit()
    print('Database initialized with sample data')

if __name__ == '__main__':
    #port = int(os.getenv("PORT", 5000))
    #app.run(host='0.0.0.0', port=port)
    app.run(debug=True)
