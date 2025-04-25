from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy 
from flask_login import ( 
    LoginManager, 
    UserMixin, 
    login_user, 
    login_required, 
    logout_user, 
    current_user 
) 
from datetime import datetime 
import re 
import tempfile
import os
import subprocess
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash # Added for password hashing

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder="templates") 

# Configuration
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your-secret-key")
# Use PostgreSQL in production, SQLite in development
if os.getenv("DATABASE_URL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///orders.db"
    
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False 

# Custom flash message categories
app.config['MESSAGE_CATEGORIES'] = {
    'success': 'positive',  # Green messages
    'error': 'negative',    # Red messages
    'info': 'info',        # Blue messages
    'warning': 'warning'    # Yellow messages
}

db = SQLAlchemy(app) 

# Setup Flask-Login 
login_manager = LoginManager(app) 
login_manager.login_view = "login" 

# Initialize token serializer (outside routes, needs app context technically but SECRET_KEY is enough here)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

######################################## 
# Database Models 
######################################## 
class User(db.Model, UserMixin): 
    __tablename__ = 'user'
    __table_args__ = {'quote': True}  # This will properly quote the table name
    id = db.Column(db.Integer, primary_key=True) 
    username = db.Column(db.String(50), unique=True, nullable=False)  # Auto-populated from selected Site. 
    email = db.Column(db.String(120), nullable=False) 
    password = db.Column(db.String(50), nullable=False)  # For demo purposes only. 
    role = db.Column(db.String(20), nullable=False)  # "Admin" or "Manager" 
    site = db.Column(db.String(100), nullable=False)  # Store the selected site
    def __repr__(self): 
        return f"<User {self.username} - {self.role}>" 

class Order(db.Model): 
    __tablename__ = 'order'
    __table_args__ = {'quote': True}  # This will properly quote the table name
    id = db.Column(db.Integer, primary_key=True) 
    supplier = db.Column(db.String(100), nullable=False) 
    description = db.Column(db.String(500), nullable=False) 
    amount = db.Column(db.Float, nullable=False)  # Total Amount field (Incl.)
    submitter = db.Column(db.String(50), nullable=False)  # Holds the Site selected. 
    site = db.Column(db.String(100), nullable=False)  # Store the selected site
    created_at = db.Column(db.DateTime, default=datetime.now) 
    status = db.Column(db.String(20), default="pending") 
    approver = db.Column(db.String(50)) 
    approved_at = db.Column(db.DateTime, nullable=True) 
    submitter_emp_number = db.Column(db.String(20), nullable=True) 
    submitter_emp_name = db.Column(db.String(100), nullable=True) 
    approver_emp_number = db.Column(db.String(20), nullable=True) 
    approver_emp_name = db.Column(db.String(100), nullable=True) 
    def __repr__(self): 
        return f"<Order {self.id} - {self.status}>" 

######################################## 
# SMTP Email Helper
########################################
def send_via_smtp(recipient, subject, body, sender=None):
    """
    Send an email using SMTP with credentials from environment variables.
    """
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port_str = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD") # Use App Password if MFA is enabled

    if not all([smtp_server, smtp_port_str, smtp_username, smtp_password]):
        print("SMTP configuration missing in environment variables. Cannot send email.")
        flash("Email notification configuration error. Please contact admin.", "error")
        return False

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        print(f"Invalid SMTP_PORT: {smtp_port_str}. Must be an integer.")
        flash("Email notification configuration error (port). Please contact admin.", "error")
        return False

    # Use the configured SMTP username as the default sender if none is provided
    actual_sender = sender or smtp_username

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = actual_sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        print(f"Attempting to send email via {smtp_server}:{smtp_port} from {actual_sender} to {recipient}")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable security
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully via SMTP.")
        return True

    except smtplib.SMTPAuthenticationError:
        print("SMTP Authentication Error: Check username/password (use App Password if MFA enabled).")
        flash("Failed to send email notification due to authentication error.", "error")
        return False
    except smtplib.SMTPConnectError:
        print(f"SMTP Connection Error: Could not connect to {smtp_server}:{smtp_port}.")
        flash("Failed to send email notification due to connection error.", "error")
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"General SMTP Error: {error_msg}")
        flash("An unexpected error occurred while sending the email notification.", "error")
        return False

######################################## 
# User Loader for Flask-Login 
######################################## 
@login_manager.user_loader 
def load_user(user_id): 
    return User.query.get(int(user_id)) 

######################################## 
# Routes 
######################################## 
@app.route("/") 
@login_required 
def index(): 
    # Filter orders by user's site
    orders = Order.query.filter_by(site=current_user.site).order_by(Order.created_at.desc()).all() 
    # Attach the submitter's role to each order for approval button logic. 
    for order in orders: 
        user = User.query.filter_by(username=order.submitter).first() 
        if user: 
            order.submitter_role = user.role 
        else: 
            order.submitter_role = "Unknown" 
    return render_template("index.html", orders=orders) 

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username") # This is the email
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()

        # *** Use check_password_hash for verification ***
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Welcome back! You have successfully logged in.", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password. Please try again.", "error")
    return render_template("login.html")

@app.route("/logout") 
@login_required 
def logout(): 
    logout_user() 
    flash("You have been successfully logged out. Have a great day!", "success") 
    return redirect(url_for("login")) 

# Registration Route 
@app.route("/register", methods=["GET", "POST"]) 
def register(): 
    sites = { 
        "TWT Alberton": "TWT Alberton",
        "TWT Amanzimtoti": "TWT Amanzimtoti",
        "TWT Balfour Park": "TWT Balfour Park",
        "TWT Bedfordview": "TWT Bedfordview",
        "TWT Bellville": "TWT Bellville",
        "TWT Benoni": "TWT Benoni",
        "TWT Boksburg": "TWT Boksburg",
        "TWT Brits": "TWT Brits",
        "TWT Broadacres": "TWT Broadacres",
        "TWT Canal Walk": "TWT Canal Walk",
        "TWT Cape Gate": "TWT Cape Gate",
        "TWT Cape Town": "TWT Cape Town",
        "TWT Centurion": "TWT Centurion",
        "TWT Centurion Lifestyle": "TWT Centurion Lifestyle",
        "TWT Claremont": "TWT Claremont",
        "TWT Cradlestone": "TWT Cradlestone",
        "TWT Cresta": "TWT Cresta",
        "TWT Durban": "TWT Durban",
        "TWT Durbanville": "TWT Durbanville",
        "TWT Eastgate": "TWT Eastgate",
        "TWT Festival Mall": "TWT Festival Mall",
        "TWT Fordsburg": "TWT Fordsburg",
        "TWT Fourways": "TWT Fourways",
        "TWT George": "TWT George",
        "TWT Gezina": "TWT Gezina",
        "TWT Greenstone": "TWT Greenstone",
        "TWT Groblersdal": "TWT Groblersdal",
        "TWT Hammanskraal": "TWT Hammanskraal",
        "TWT Hatfield": "TWT Hatfield",
        "TWT Kempton Park": "TWT Kempton Park",
        "TWT Keywest": "TWT Keywest",
        "TWT Killarney Mall": "TWT Killarney Mall",
        "TWT Klerksdorp": "TWT Klerksdorp",
        "TWT La Lucia": "TWT La Lucia",
        "TWT Lephalale": "TWT Lephalale",
        "TWT Lynnwood": "TWT Lynnwood",
        "TWT Mall at Reds": "TWT Mall at Reds",
        "TWT Meadowdale": "TWT Meadowdale",
        "TWT Melrose": "TWT Melrose",
        "TWT Menlyn": "TWT Menlyn",
        "TWT Middelburg": "TWT Middelburg",
        "TWT Midrand": "TWT Midrand",
        "TWT Modimolle": "TWT Modimolle",
        "TWT Mokopane": "TWT Mokopane",
        "TWT Montana": "TWT Montana",
        "TWT Mosselbay": "TWT Mosselbay",
        "TWT Mt Edgecombe": "TWT Mt Edgecombe",
        "TWT Musina": "TWT Musina",
        "TWT N1 City": "TWT N1 City",
        "TWT Nelspruit CBD": "TWT Nelspruit CBD",
        "TWT Newmarket": "TWT Newmarket",
        "TWT Noordhoek": "TWT Noordhoek",
        "TWT Paarl": "TWT Paarl",
        "TWT Paarl Mall": "TWT Paarl Mall",
        "TWT Parkdene": "TWT Parkdene",
        "TWT Parklands": "TWT Parklands",
        "TWT PE Heugh Road": "TWT PE Heugh Road",
        "TWT Pinetown": "TWT Pinetown",
        "TWT Polokwane": "TWT Polokwane",
        "TWT Port Elizabeth": "TWT Port Elizabeth",
        "TWT Potchefstroom": "TWT Potchefstroom",
        "TWT Pretoria CBD": "TWT Pretoria CBD",
        "TWT Randburg": "TWT Randburg",
        "TWT Randfontein": "TWT Randfontein",
        "TWT Raslouw": "TWT Raslouw",
        "TWT Riverside": "TWT Riverside",
        "TWT Rivonia": "TWT Rivonia",
        "TWT Rosebank": "TWT Rosebank",
        "TWT Rustenburg": "TWT Rustenburg",
        "TWT Sandhurst": "TWT Sandhurst",
        "TWT Sandton": "TWT Sandton",
        "TWT Savannah": "TWT Savannah",
        "TWT Silverlakes": "TWT Silverlakes",
        "TWT Somerset": "TWT Somerset",
        "TWT Springfield": "TWT Springfield",
        "TWT Springs": "TWT Springs",
        "TWT Stellenbosch": "TWT Stellenbosch",
        "TWT Strijdom Park": "TWT Strijdom Park",
        "TWT Strubens Valley": "TWT Strubens Valley",
        "TWT Sunninghill": "TWT Sunninghill",
        "TWT Tableview": "TWT Tableview",
        "TWT Tembisa": "TWT Tembisa",
        "TWT The Glen": "TWT The Glen",
        "TWT Tokai": "TWT Tokai",
        "TWT Tygervalley": "TWT Tygervalley",
        "TWT Umhlanga": "TWT Umhlanga",
        "TWT Vanderbijlpark": "TWT Vanderbijlpark",
        "TWT Walmer": "TWT Walmer",
        "TWT Westgate": "TWT Westgate",
        "TWT Wonderboom": "TWT Wonderboom",
        "TWT Wonderpark": "TWT Wonderpark",
        "TWT Woodlands Mall": "TWT Woodlands Mall",
        "TWT Woodmead": "TWT Woodmead"
    } 
    roles = { 
        "Admin": "Admin", 
        "Manager": "Manager" 
    } 
    if request.method == "POST": 
        site = request.form.get("site") 
        selected_role = request.form.get("role") 
        email = request.form.get("email") 
        username = request.form.get("username")  # This will be the email address
        password = request.form.get("password") 
        
        # Improved validation messages
        if site not in sites: 
            flash("Please select a valid Tiger Wheel & Tyre site from the list.", "error") 
            return render_template("register.html", sites=sites, roles=roles) 
        if selected_role not in roles: 
            flash("Please select either Admin or Manager role.", "error") 
            return render_template("register.html", sites=sites, roles=roles) 
        if not email or "@" not in email: 
            flash("Please provide a valid email address (e.g., name@company.com).", "error") 
            return render_template("register.html", sites=sites, roles=roles) 
        
        # Password validation with clearer messages
        password_errors = []
        if len(password) < 8:
            password_errors.append("at least 8 characters")
        if not re.search(r'[A-Z]', password):
            password_errors.append("one uppercase letter")
        if not re.search(r'\d', password):
            password_errors.append("one number")
        if not re.search(r'[\W_]', password):
            password_errors.append("one special character")
            
        if password_errors:
            flash(f"Password must contain {', '.join(password_errors)}.", "error")
            return render_template("register.html", sites=sites, roles=roles)

        # Check if email is already registered
        if User.query.filter_by(username=email).first(): 
            flash("An account with this email address already exists. Please log in.", "danger") 
            return redirect(url_for("login")) 

        # *** Hash the password before saving ***
        hashed_password = generate_password_hash(password)

        # Create new user with email as username and hashed password
        new_user = User(
            username=email,  # Use email as username
            email=email,
            password=hashed_password, # Store the hash
            role=selected_role,
            site=site
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login")) 
    return render_template("register.html", sites=sites, roles=roles) 

# Create Order Route with Submitter Employee Details and new Item Details 
@app.route("/create", methods=["GET", "POST"]) 
@login_required 
def create_order():
    if request.method == "POST":
        supplier = request.form.get("supplier", "").strip()
        if not supplier:
            flash("Supplier is required.", "danger")
            return render_template("create_order.html")
        
        # Get the user's site from their account
        user = User.query.filter_by(username=current_user.username).first()
        if not user:
            flash("User account not found.", "danger")
            return redirect(url_for("index"))
        
        # Gather item details arrays from the new item table. 
        item_descs = request.form.getlist("item_desc[]")
        item_qtys = request.form.getlist("item_qty[]")
        item_unit_costs = request.form.getlist("item_unit_cost[]")
        item_total_costs = request.form.getlist("item_total_cost[]")
        
        # Validate that at least one item description is provided.
        if not item_descs or all(d.strip() == "" for d in item_descs):
            flash("At least one item description is required.", "danger")
            return render_template("create_order.html")
        
        # Combine each row's data into one description string.
        description_lines = []
        for i in range(len(item_descs)):
            qty = item_qtys[i].strip() if i < len(item_qtys) else ""
            desc = item_descs[i].strip()
            unit_cost = item_unit_costs[i].strip() if i < len(item_unit_costs) else ""
            total_cost = item_total_costs[i].strip() if i < len(item_total_costs) else ""
            if desc != "":
                line = f"QTY: {qty}, Description: {desc}, Unit Cost Excl.: {unit_cost}, Total Unit Cost Excl.: {total_cost}"
                description_lines.append(line)
        description = "\n".join(description_lines)
        
        # Get the total amount incl. from the summary field.
        amount_str = request.form.get("amount", "").strip()
        if not amount_str:
            flash("Total Amount Incl. is required.", "danger")
            return render_template("create_order.html")
        try:
            amount = float(amount_str)
        except ValueError:
            flash("Please enter a valid number for the Total Amount Incl.", "danger")
            return render_template("create_order.html")
            
        submitter_emp_number = request.form.get("submitter_emp_number")
        submitter_emp_name = request.form.get("submitter_emp_name")
        if not submitter_emp_number or not submitter_emp_name:
            flash("Employee Number and Employee Name are required for submission.", "danger")
            return render_template("create_order.html")
        
        new_order = Order(
            supplier=supplier,
            description=description,
            amount=amount,
            submitter=current_user.username,
            site=user.site,  # Store the user's site
            submitter_emp_number=submitter_emp_number,
            submitter_emp_name=submitter_emp_name
        )
        db.session.add(new_order)
        db.session.commit()
        flash("Order created successfully!", "success")
        
        # Find the approver at the same site with the opposite role
        approver_role = "Manager" if current_user.role == "Admin" else "Admin"
        approver = User.query.filter_by(site=user.site, role=approver_role).first()
        
        if approver:
            # Email notification to the approver at the same site
            subject = "New Order Awaiting Approval"
            body = (
                f"Dear {approver_role},\n\n"
                f"A new order created by {current_user.username} ({current_user.role}) at {user.site} is awaiting your approval.\n"
                f"Order ID: {new_order.id}\n"
                f"Site: {new_order.site}\n"
                f"Supplier: {new_order.supplier}\n"
                f"Description:\n{new_order.description}\n"
                f"Total Amount Incl.: {new_order.amount:.2f}\n"
                f"Submitter (Emp #, Name): {new_order.submitter_emp_number}, {new_order.submitter_emp_name}\n\n"
                "Please log in to review and approve the order."
            )
            if send_via_smtp(recipient=approver.email, subject=subject, body=body):
                flash(f"Notification sent to {approver.email} for approval.", "info")
        else:
            flash(f"No {approver_role} found at {user.site} to notify.", "warning")
            
        return redirect(url_for("index"))
    return render_template("create_order.html")

# Approve Order Route with Role Check Based on Submitter's Role 
@app.route("/approve/<int:order_id>", methods=["POST"]) 
@login_required 
def approve_order(order_id): 
    order = Order.query.get_or_404(order_id) 
    if order.status != "pending": 
        flash("This order has already been processed.", "warning") 
        return redirect(url_for("index")) 
    submitter_obj = User.query.filter_by(username=order.submitter).first() 
    if not submitter_obj: 
        flash("Submitter account not found.", "danger") 
        return redirect(url_for("index")) 
    # Allow approval only if the current user's role is the opposite of the submitter's. 
    if (submitter_obj.role == "Admin" and current_user.role == "Manager") or \
       (submitter_obj.role == "Manager" and current_user.role == "Admin"): 
        approver_emp_number = request.form.get("approver_emp_number") 
        approver_emp_name = request.form.get("approver_emp_name") 
        if not approver_emp_number or not approver_emp_name: 
            flash("Employee Number and Employee Name are required for approval.", "danger") 
            return redirect(url_for("index")) 
        order.status = "approved" 
        order.approver = current_user.username 
        order.approved_at = datetime.now() 
        order.approver_emp_number = approver_emp_number 
        order.approver_emp_name = approver_emp_name 
        db.session.commit() 
        flash(f"Order #{order.id} has been successfully approved.", "success") 
        
        # Send email to the submitter
        subject = "Your Order Has Been Approved"
        body = (
            f"Dear {submitter_obj.role},\n\n"
            f"Your order (ID: {order.id}) at {order.site} has been approved by {current_user.username} ({current_user.role}).\n"
            f"Approver (Emp #, Name): {order.approver_emp_number}, {order.approver_emp_name}\n"
            "You can now proceed to print the order.\n\n"
            "Best regards,\nOrder Management System"
        )
        if send_via_smtp(recipient=submitter_obj.email, subject=subject, body=body):
            flash(f"Notification sent to {submitter_obj.email} regarding approval.", "info")
    else: 
        flash("You are not authorized to approve this order.", "danger") 
    return redirect(url_for("index")) 

# Decline Order Route with Role Check 
@app.route("/decline/<int:order_id>", methods=["POST"])
@login_required
def decline_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status != "pending": 
        flash("This order has already been processed.", "warning") 
        return redirect(url_for("index")) 
    submitter_obj = User.query.filter_by(username=order.submitter).first()
    if not submitter_obj:
        flash("Submitter account not found.", "danger")
        return redirect(url_for("index"))
    if (submitter_obj.role == "Admin" and current_user.role == "Manager") or \
       (submitter_obj.role == "Manager" and current_user.role == "Admin"):
        approver_emp_number = request.form.get("approver_emp_number")
        approver_emp_name = request.form.get("approver_emp_name")
        if not approver_emp_number or not approver_emp_name:
            flash("Employee Number and Employee Name are required for decline.", "danger")
            return redirect(url_for("index"))
        order.status = "declined"
        order.approver = current_user.username
        order.approved_at = datetime.now()
        order.approver_emp_number = approver_emp_number
        order.approver_emp_name = approver_emp_name
        db.session.commit()
        flash(f"Order #{order.id} has been declined.", "error")
        
        # Send email to the submitter
        subject = "Your Order Has Been Declined"
        body = (
            f"Dear {submitter_obj.role},\n\n"
            f"Your order (ID: {order.id}) at {order.site} has been declined by {current_user.username} ({current_user.role}).\n"
            f"Decliner (Emp #, Name): {order.approver_emp_number}, {order.approver_emp_name}\n\n"
            "Please contact your approver for more information."
        )
        if send_via_smtp(recipient=submitter_obj.email, subject=subject, body=body):
            flash(f"Notification sent to {submitter_obj.email} regarding decline.", "info")
    else:
        flash("You are not authorized to decline this order.", "danger")
    return redirect(url_for("index"))

@app.route("/print/<int:order_id>") 
@login_required 
def print_order(order_id): 
    order = Order.query.get_or_404(order_id) 
    return render_template("print_order.html", order=order) 

# Send to Supplier Route using Headless Chrome to generate PDF
@app.route("/send_to_supplier/<int:order_id>")
@login_required
def send_to_supplier(order_id):
    """
    Generate PDF for order and prepare email to supplier.
    *** Needs significant update to use SMTP and handle attachments ***
    """
    flash("Send to Supplier functionality needs update for SMTP.", "warning")
    # Placeholder - redirect back or show message
    return redirect(url_for('index'))

@app.route("/health")
def health_check():
    return "OK", 200

@app.route("/healthz")
def healthz_check():
    return "OK", 200

def setup_users():
    # No longer creating default users
    # Users should register through the registration page
    pass

def init_db():
    with app.app_context():
        try:
            # Create all tables
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully")
            
            # Setup initial users if needed
            setup_users()
            print("Database initialization completed successfully")
            
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            # Don't raise the error, just log it
            # This allows the application to start even if there are database issues
            pass

# Initialize the database when the application starts
if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
else:
    # This will run when the app is started by Gunicorn on Render
    init_db()

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        site = request.form.get("site")

        # Find user with matching email and site
        user = User.query.filter_by(email=email, site=site).first()

        if user:
            # Generate a time-sensitive token containing the user's ID
            token = s.dumps(user.id, salt='password-reset-salt') # Salt adds extra security
            reset_url = url_for('reset_password', token=token, _external=True) # _external=True creates full URL

            # Send password reset email
            subject = "Password Reset Request - Order Management System"
            body = f"""Dear {user.username},

Please click the link below to reset your password. This link is valid for 1 hour.

{reset_url}

If you did not request this change, please ignore this email.

Best regards,
Order Management System"""

            send_via_smtp(user.email, subject, body)
            # No specific success flash here for security

        # Always show a generic message to prevent user enumeration
        flash("If an account with that email and site exists, a password reset link has been sent.", "info")
        return redirect(url_for("login"))

    # GET request - show the form to request a reset link
    # Regenerate sites dictionary here as it's needed by the template
    sites = {
        "TWT Alberton": "TWT Alberton",
        "TWT Amanzimtoti": "TWT Amanzimtoti",
        "TWT Balfour Park": "TWT Balfour Park",
        "TWT Bedfordview": "TWT Bedfordview",
        "TWT Bellville": "TWT Bellville",
        "TWT Benoni": "TWT Benoni",
        "TWT Boksburg": "TWT Boksburg",
        "TWT Brits": "TWT Brits",
        "TWT Broadacres": "TWT Broadacres",
        "TWT Canal Walk": "TWT Canal Walk",
        "TWT Cape Gate": "TWT Cape Gate",
        "TWT Cape Town": "TWT Cape Town",
        "TWT Centurion": "TWT Centurion",
        "TWT Centurion Lifestyle": "TWT Centurion Lifestyle",
        "TWT Claremont": "TWT Claremont",
        "TWT Cradlestone": "TWT Cradlestone",
        "TWT Cresta": "TWT Cresta",
        "TWT Durban": "TWT Durban",
        "TWT Durbanville": "TWT Durbanville",
        "TWT Eastgate": "TWT Eastgate",
        "TWT Festival Mall": "TWT Festival Mall",
        "TWT Fordsburg": "TWT Fordsburg",
        "TWT Fourways": "TWT Fourways",
        "TWT George": "TWT George",
        "TWT Gezina": "TWT Gezina",
        "TWT Greenstone": "TWT Greenstone",
        "TWT Groblersdal": "TWT Groblersdal",
        "TWT Hammanskraal": "TWT Hammanskraal",
        "TWT Hatfield": "TWT Hatfield",
        "TWT Kempton Park": "TWT Kempton Park",
        "TWT Keywest": "TWT Keywest",
        "TWT Killarney Mall": "TWT Killarney Mall",
        "TWT Klerksdorp": "TWT Klerksdorp",
        "TWT La Lucia": "TWT La Lucia",
        "TWT Lephalale": "TWT Lephalale",
        "TWT Lynnwood": "TWT Lynnwood",
        "TWT Mall at Reds": "TWT Mall at Reds",
        "TWT Meadowdale": "TWT Meadowdale",
        "TWT Melrose": "TWT Melrose",
        "TWT Menlyn": "TWT Menlyn",
        "TWT Middelburg": "TWT Middelburg",
        "TWT Midrand": "TWT Midrand",
        "TWT Modimolle": "TWT Modimolle",
        "TWT Mokopane": "TWT Mokopane",
        "TWT Montana": "TWT Montana",
        "TWT Mosselbay": "TWT Mosselbay",
        "TWT Mt Edgecombe": "TWT Mt Edgecombe",
        "TWT Musina": "TWT Musina",
        "TWT N1 City": "TWT N1 City",
        "TWT Nelspruit CBD": "TWT Nelspruit CBD",
        "TWT Newmarket": "TWT Newmarket",
        "TWT Noordhoek": "TWT Noordhoek",
        "TWT Paarl": "TWT Paarl",
        "TWT Paarl Mall": "TWT Paarl Mall",
        "TWT Parkdene": "TWT Parkdene",
        "TWT Parklands": "TWT Parklands",
        "TWT PE Heugh Road": "TWT PE Heugh Road",
        "TWT Pinetown": "TWT Pinetown",
        "TWT Polokwane": "TWT Polokwane",
        "TWT Port Elizabeth": "TWT Port Elizabeth",
        "TWT Potchefstroom": "TWT Potchefstroom",
        "TWT Pretoria CBD": "TWT Pretoria CBD",
        "TWT Randburg": "TWT Randburg",
        "TWT Randfontein": "TWT Randfontein",
        "TWT Raslouw": "TWT Raslouw",
        "TWT Riverside": "TWT Riverside",
        "TWT Rivonia": "TWT Rivonia",
        "TWT Rosebank": "TWT Rosebank",
        "TWT Rustenburg": "TWT Rustenburg",
        "TWT Sandhurst": "TWT Sandhurst",
        "TWT Sandton": "TWT Sandton",
        "TWT Savannah": "TWT Savannah",
        "TWT Silverlakes": "TWT Silverlakes",
        "TWT Somerset": "TWT Somerset",
        "TWT Springfield": "TWT Springfield",
        "TWT Springs": "TWT Springs",
        "TWT Stellenbosch": "TWT Stellenbosch",
        "TWT Strijdom Park": "TWT Strijdom Park",
        "TWT Strubens Valley": "TWT Strubens Valley",
        "TWT Sunninghill": "TWT Sunninghill",
        "TWT Tableview": "TWT Tableview",
        "TWT Tembisa": "TWT Tembisa",
        "TWT The Glen": "TWT The Glen",
        "TWT Tokai": "TWT Tokai",
        "TWT Tygervalley": "TWT Tygervalley",
        "TWT Umhlanga": "TWT Umhlanga",
        "TWT Vanderbijlpark": "TWT Vanderbijlpark",
        "TWT Walmer": "TWT Walmer",
        "TWT Westgate": "TWT Westgate",
        "TWT Wonderboom": "TWT Wonderboom",
        "TWT Wonderpark": "TWT Wonderpark",
        "TWT Woodlands Mall": "TWT Woodlands Mall",
        "TWT Woodmead": "TWT Woodmead"
    }
    return render_template("forgot_password.html", sites=sites)

# New route for handling the actual password reset
@app.route('/reset_password/<token>', methods=["GET", "POST"])
def reset_password(token):
    try:
        user_id = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception as e:
        print(f"Password reset token error: {e}")
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        # Validate password complexity (reuse logic from registration)
        password_errors = []
        if len(new_password) < 8:
            password_errors.append("at least 8 characters")
        if not re.search(r'[A-Z]', new_password):
            password_errors.append("one uppercase letter")
        if not re.search(r'\d', new_password):
            password_errors.append("one number")
        if not re.search(r'[\W_]', new_password):
            password_errors.append("one special character")

        if password_errors:
            flash(f"Password must contain {', '.join(password_errors)}.", "error")
            return render_template('reset_password.html', token=token)

        # *** Hash the new password before updating ***
        hashed_password = generate_password_hash(new_password)
        user.password = hashed_password # Store the hash
        db.session.commit()

        # (Optional: Send confirmation email that password was changed)
        # subject_confirm = "Password Changed Confirmation"
        # body_confirm = "Your password has been successfully changed."
        # send_via_smtp(user.email, subject_confirm, body_confirm)

        flash('Your password has been successfully reset. Please log in.', 'success')
        return redirect(url_for('login'))

    # GET request: Show the password reset form
    return render_template('reset_password.html', token=token)