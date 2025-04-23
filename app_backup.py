from flask import Flask, render_template, request, redirect, url_for, flash 
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

app = Flask(__name__, template_folder="templates") 
app.config["SECRET_KEY"] = "your-secret-key"  # Replace with your secure key 
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///orders.db" 
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False 
db = SQLAlchemy(app) 

# Setup Flask-Login 
login_manager = LoginManager(app) 
login_manager.login_view = "login" 

######################################## 
# Database Models 
######################################## 
class User(db.Model, UserMixin): 
    id = db.Column(db.Integer, primary_key=True) 
    username = db.Column(db.String(50), unique=True, nullable=False)  # Auto-populated from selected Site. 
    email = db.Column(db.String(120), nullable=False) 
    password = db.Column(db.String(50), nullable=False)  # For demo purposes only. 
    role = db.Column(db.String(20), nullable=False)  # "Admin" or "Manager" 
    def __repr__(self): 
        return f"<User {self.username} - {self.role}>" 

class Order(db.Model): 
    id = db.Column(db.Integer, primary_key=True) 
    supplier = db.Column(db.String(100), nullable=False) 
    description = db.Column(db.String(500), nullable=False) 
    amount = db.Column(db.Float, nullable=False)  # Total Amount field. 
    submitter = db.Column(db.String(50), nullable=False)  # Holds the Site selected. 
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
# Outlook Email Helper Using COM 
######################################## 
def send_email_via_outlook(recipient, subject, body, sender=None): 
    try: 
        import pythoncom 
        pythoncom.CoInitialize() 
        import win32com.client as win32 
        outlook = win32.Dispatch('Outlook.Application') 
        mail = outlook.CreateItem(0)  # 0: Outlook mail item. 
        mail.To = recipient 
        mail.Subject = subject 
        mail.Body = body 
        if sender and sender.lower() != recipient.lower(): 
            mail.SentOnBehalfOfName = sender 
        print(f"Attempting to send email to {recipient} with subject '{subject}'...") 
        mail.Send() 
        print(f"Email successfully sent to {recipient} with subject '{subject}'") 
        pythoncom.CoUninitialize() 
    except Exception as e: 
        print("Error sending email:", e) 

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
    orders = Order.query.order_by(Order.created_at.desc()).all() 
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
        username = request.form.get("username") 
        password = request.form.get("password") 
        user = User.query.filter_by(username=username).first() 
        if user and user.password == password: 
            login_user(user) 
            flash("Logged in successfully.", "success") 
            return redirect(url_for("index")) 
        else: 
            flash("Invalid username or password.", "danger") 
    return render_template("login.html") 

@app.route("/logout") 
@login_required 
def logout(): 
    logout_user() 
    flash("Logged out successfully.", "success") 
    return redirect(url_for("login")) 

# Registration Route 
@app.route("/register", methods=["GET", "POST"]) 
def register(): 
    sites = { 
        "TWT Durbanville": "TWT Durbanville", 
        "TWT Cape Gate": "TWT Cape Gate" 
    } 
    roles = { 
        "Admin": "Admin", 
        "Manager": "Manager" 
    } 
    if request.method == "POST": 
        site = request.form.get("site") 
        selected_role = request.form.get("role") 
        email = request.form.get("email") 
        password = request.form.get("password") 
        if site not in sites: 
            flash("Invalid site selection.", "danger") 
            return render_template("register.html", sites=sites, roles=roles) 
        if selected_role not in roles: 
            flash("Invalid role selection.", "danger") 
            return render_template("register.html", sites=sites, roles=roles) 
        if not email or "@" not in email: 
            flash("Please provide a valid email address.", "danger") 
            return render_template("register.html", sites=sites, roles=roles) 
        if len(password) < 8: 
            flash("Password must be at least 8 characters long.", "danger") 
            return render_template("register.html", sites=sites, roles=roles) 
        if not re.search(r'[A-Z]', password): 
            flash("Password must include at least one uppercase letter.", "danger") 
            return render_template("register.html", sites=sites, roles=roles) 
        if not re.search(r'\d', password): 
            flash("Password must include at least one number.", "danger") 
            return render_template("register.html", sites=sites, roles=roles) 
        if not re.search(r'[\W_]', password): 
            flash("Password must include at least one special character.", "danger") 
            return render_template("register.html", sites=sites, roles=roles) 
        username = site  # Username is derived from the selected site. 
        if User.query.filter_by(username=username).first(): 
            flash("An account for this site already exists. Please log in.", "danger") 
            return redirect(url_for("login")) 
        new_user = User(username=username, email=email, password=password, role=selected_role) 
        db.session.add(new_user) 
        db.session.commit() 
        flash("Account created successfully! Please log in.", "success") 
        return redirect(url_for("login")) 
    return render_template("register.html", sites=sites, roles=roles) 

# Create Order Route with Submitter Employee Details 
@app.route("/create", methods=["GET", "POST"]) 
@login_required 
def create_order(): 
    if request.method == "POST": 
        supplier = request.form.get("supplier", "").strip() 
        if not supplier: 
            flash("Supplier is required.", "danger") 
            return render_template("create_order.html") 
        descriptions = request.form.getlist("description") 
        description = "\n".join([d.strip() for d in descriptions if d.strip() != ""]) 
        if not description: 
            flash("At least one Description is required.", "danger") 
            return render_template("create_order.html") 
        amount_str = request.form.get("amount") 
        if not amount_str: 
            flash("Total Amount is required.", "danger") 
            return render_template("create_order.html") 
        try: 
            amount = float(amount_str) 
        except ValueError: 
            flash("Please enter a valid number for the Total Amount.", "danger") 
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
            submitter_emp_number=submitter_emp_number, 
            submitter_emp_name=submitter_emp_name 
        ) 
        db.session.add(new_order) 
        db.session.commit() 
        flash("Order created successfully!", "success") 
        # Email notification to the opposing role. 
        if current_user.role == "Admin": 
            subject = "New Order Awaiting Approval" 
            body = ( 
                f"Dear Manager,\n\n" 
                f"A new order created by {current_user.username} (Admin) is awaiting your approval.\n" 
                f"Order ID: {new_order.id}\n" 
                f"Supplier: {new_order.supplier}\n" 
                f"Description:\n{new_order.description}\n" 
                f"Total Amount: {new_order.amount:.2f}\n" 
                f"Submitter (Emp #, Name): {new_order.submitter_emp_number}, {new_order.submitter_emp_name}\n\n" 
                "Please log in to review and approve the order." 
            ) 
            send_email_via_outlook(recipient="deand@twt.to", subject=subject, body=body, sender="deand@twt.to") 
        elif current_user.role == "Manager": 
            subject = "New Order Awaiting Approval" 
            body = ( 
                f"Dear Admin,\n\n" 
                f"A new order created by {current_user.username} (Manager) is awaiting your approval.\n" 
                f"Order ID: {new_order.id}\n" 
                f"Supplier: {new_order.supplier}\n" 
                f"Description:\n{new_order.description}\n" 
                f"Total Amount: {new_order.amount:.2f}\n" 
                f"Submitter (Emp #, Name): {new_order.submitter_emp_number}, {new_order.submitter_emp_name}\n\n" 
                "Please log in to review and approve the order." 
            ) 
            send_email_via_outlook(recipient="deand@twt.to", subject=subject, body=body, sender="deand@twt.to") 
        flash("Notification sent for approval.", "info") 
        return redirect(url_for("index")) 
    return render_template("create_order.html") 

# Approve Order Route with Role Check Based on Submitter's Role 
@app.route("/approve/<int:order_id>", methods=["POST"]) 
@login_required 
def approve_order(order_id): 
    order = Order.query.get_or_404(order_id) 
    submitter_obj = User.query.filter_by(username=order.submitter).first() 
    if not submitter_obj: 
        flash("Submitter account not found.", "danger") 
        return redirect(url_for("index")) 
    # Allow approval only if the current user's role is the opposite of the submitter's. 
    if (submitter_obj.role == "Admin" and current_user.role == "Manager") or \
       (submitter_obj.role == "Manager" and current_user.role == "Admin"): 
        if order.status == "pending": 
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
            flash(f"Order {order.id} approved!", "success") 
            subject = "Your Order Has Been Approved" 
            if submitter_obj.role == "Admin": 
                body = ( 
                    f"Dear Admin,\n\n" 
                    f"Your order (ID: {order.id}) has been approved by the Manager ({current_user.username}).\n" 
                    f"Approver (Emp #, Name): {order.approver_emp_number}, {order.approver_emp_name}\n" 
                    "You can now proceed to print the order.\n\n" 
                    "Best regards,\nOrder Management System" 
                ) 
            else: 
                body = ( 
                    f"Dear Manager,\n\n" 
                    f"Your order (ID: {order.id}) has been approved by the Admin ({current_user.username}).\n" 
                    f"Approver (Emp #, Name): {order.approver_emp_number}, {order.approver_emp_name}\n" 
                    "You can now proceed to print the order.\n\n" 
                    "Best regards,\nOrder Management System" 
                ) 
            send_email_via_outlook(recipient="deand@twt.to", subject=subject, body=body, sender="deand@twt.to") 
            flash("Notification sent regarding approval.", "info") 
        else: 
            flash("Order has already been approved.", "warning") 
    else: 
        flash("You are not authorized to approve this order.", "danger") 
    return redirect(url_for("index")) 

@app.route("/print/<int:order_id>") 
@login_required 
def print_order(order_id): 
    order = Order.query.get_or_404(order_id) 
    return render_template("print_order.html", order=order) 

def setup_users(): 
    admin = User.query.filter_by(username="Admin").first() 
    if not admin: 
        admin = User(username="Admin", email="deand@twt.to", password="Admin", role="Admin") 
        db.session.add(admin) 
    manager = User.query.filter_by(username="Manager").first() 
    if not manager: 
        manager = User(username="Manager", email="deand@twt.to", password="Manager", role="Manager") 
        db.session.add(manager) 
    db.session.commit() 

if __name__ == "__main__": 
    with app.app_context(): 
        db.create_all() 
        setup_users() 
    app.run(debug=True)